

import enum
from traceback import print_stack


class BaseNode:
    def __init__(self, name, type) -> None:
        self.name = name
        self.type = type
        self.scope = None

        self._driver = []


# Funtional Box
class SimFuncBox(BaseNode):
    def __init__(self, name, type) -> None:
        super().__init__(name, type)


# Variable Node : Single Sign
class SimVarNode(BaseNode):
       
    def __init__(self, name, type, default) -> None:
        super().__init__(name, type)

        self.default = default
        
        self._is_packet_ptr = (type.spelling == 'PacketPtr')
        self._uncertained = False

    # {cond : str , stmt : str , prev : [...] }
    # cond == None eq to 'default'
    def add_relation(self, prev, cond = None):
        if cond :
            self._uncertained = True
        
        self._driver.append({
            "cond" : cond,
            "prev" : prev
        })
    
    def merge_node(self, another):
        self._driver += another._driver

class UryOpNode(BaseNode):
    def __init__(self, name, sub) -> None:
        super().__init__(name, None)

        self.sub = sub

class BinOpNode(BaseNode):
    def __init__(self, name, lchild, rchild) -> None:
        super().__init__(name, None)

        self.lchild = lchild
        self.rchild = rchild

class LitNode(BaseNode):
    def __init__(self, name, value) -> None:
        super().__init__(name, None)

        self.value = value

# Single Output Only T or F
class SimMuxNode(BaseNode):
    def __init__(self, name, type) -> None:
        super().__init__(name, type)
    
class SimFlowPath:
    def __init__(self, name):
        self.name = name
        self.field = ''

        self._var_refs = {}
        self._var_next = {}
        self._input = []
        self._ouput = []
        self._checked = False

    def get(self, name):
        if name in self._var_refs :
            return self._var_refs[name]
        else :
            return None

    def insert(self, node, is_input = False, is_ouput = False):
        if node.name in self._var_refs :
            self._var_refs[node.name].merge_node(node)

        else :
            self._var_refs[node.name] = node
            self._var_next[node.name] = []
            if is_input : 
                self._input.append(node.name)
            if is_ouput:
                self._ouput.append(node.name)

    def print_all_vars(self):
        print(f"Path : {self.name}")
        for var in self._var_refs :
            print(f"Var : {var} : {self._var_refs[var].type.spelling}")
            for driver in self._var_refs[var]._driver :
                print(f"Driver : {driver['cond']} : {driver['prev']}")

class SimObjInfo:

    def __init__(self, name, namespace) -> None:
        self.name = name
        self.namespace = namespace
        self.field_refs = {}
        self.path_refs = {}

    def insert_field(self, field):
        if field in self.field_refs :    
            self.field_refs[field.name].merge_node(field)

        else :
            self.field_refs[field.name] = field

        # TODO :field里的初始值也可能会有依赖关系
    def get_field(self, name):
        return self.field_refs[name]

    def insert_path(self, path):
        self.path_refs[path.name] = path

    def get_path(self, name):
        return self.path_refs[name]

class ActionBlock:
    HEAD_BLOCK = 0
    EXEC_BLOCK = 1
    LOOP_BLOCK = 2
    BRANCH_BLOCK = 3
    MEMACC_BLOCK = 4
    CALLEE_BLOCK = 5

    '''Next : (T branch, N branch), if only one branch, next = (stmt, None)'''
    def __init__(self, type) -> None:
        self.next = (None, None)
        self.cond = None
        self.stmt = []
        self.type = type

        if type not in range(6):
            raise ValueError("[SimFlowBlock] Invalid block type")

    def add_next(self, block):
        if not self.next[0] :
            self.next = (block, None)
        elif not self.next[1] :
            self.next = (self.next[0], block)
        else:
            raise ValueError("[SimFlowBlock] Too many next blocks")

    def get_next(self):
        return iter(self.next)
    
    def add_stmt(self, stmt):
        self.stmt.append(stmt)
    
    def set_cond(self, cond):
        self.cond = cond

    def get_next_cnt(self):
        return len(list(filter(None, self.next)))

HEAD_BLOCK   = ActionBlock.HEAD_BLOCK
EXEC_BLOCK   = ActionBlock.EXEC_BLOCK
LOOP_BLOCK   = ActionBlock.LOOP_BLOCK
BRANCH_BLOCK = ActionBlock.BRANCH_BLOCK
MEMACC_BLOCK = ActionBlock.MEMACC_BLOCK
CALLEE_BLOCK = ActionBlock.CALLEE_BLOCK


class ActionFlow:
    def __init__(self, name) -> None:
        self.name = name
        self.blocks = []
        self.head = None
        self.tail = None

        self._br_stack = []

    def add_block(self, block_type, cond = None):
        block = ActionBlock(block_type)
        self.blocks.append(block)
        
        if not self.head :
            self.head = block
            self.tail = block
            return

        if block.type == ActionBlock.BRANCH_BLOCK:
            if cond is not None:
                block.set_cond(cond)
            self._br_stack.append(block)
        
        self.tail.add_next(block)
        self.tail = block

    def add_stmt(self, stmt):
        if not self.tail :
            raise ValueError("[SimFlowBlock] No block to add stmt")
        
        self.tail.add_stmt(stmt)
    
    def set_cond(self, cond):
        if not self.tail or self.tail.type != ActionBlock.BRANCH_BLOCK :
            raise ValueError("[SimFlowBlock] No block to add cond")
        
        self.tail.set_cond(cond)

    def add_branch(self, block_type):
        block = ActionBlock(block_type)
        self.blocks.append(block)

        if self.tail.type != ActionBlock.BRANCH_BLOCK :
            raise ValueError("[SimFlowBlock] No branch block to add branch")
        
        self.tail.add_next(block)
        self.tail = block
    
    def ret_branch(self):
        if len(self._br_stack) == 0 :
            raise ValueError("[SimFlowBlock] No branch block to return")
        
        self.tail = self._br_stack[-1]
    
    def pop_branch(self):
        self._br_stack.pop()

    def print_flow(self):
        print(f"Action Flow : {self.name}")
        
        print_stack = []
        print_stack.append(self.head)
        while len(print_stack) > 0 :
            block = print_stack.pop()
            print(f"Block : {block.type}")
            if block.type == ActionBlock.BRANCH_BLOCK :
                print(f"Cond : {block.cond}")
            for stmt in block.stmt :
                print(f"Stmt : {stmt}")

            for next_block in block.get_next():
                if next_block :
                    print_stack.append(next_block)