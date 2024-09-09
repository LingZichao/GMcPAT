
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