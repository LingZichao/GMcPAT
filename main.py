from argparse import Action
from clang.cindex import Config, Index, CursorKind
from colorama import init, Fore

from utils import *
from ccsimobj import *


init()
Config.set_library_file('/usr/lib/llvm-15/lib/libclang.so.1')
index = Index.create()

def check_gem5_api(func_name):
    IGNORED_API_LIST = [
        'getPort',
        'getAddrRanges'
    ]

    return func_name in IGNORED_API_LIST

def check_gem5_class(class_name):
    GEM5_CLASS_LIST = [
        'System',
        'ClockedObject',
        'Port',
        'Packet',
        'gem5::PacketPtr',
        'ClockDomain',
        'ThreadContext'
    ]

    return class_name in GEM5_CLASS_LIST

def handle_class_decl(cursor, scope):
    bases = []

    simobj = SimObjInfo(cursor.spelling, CursorState.namespace)
    CursorState.simobj = simobj

    for child in cursor.get_children():
        if   child.kind == CursorKind.CXX_BASE_SPECIFIER:
            bases.append(child.type.spelling)

        elif child.kind.is_declaration():
            handle_decl(child, scope + 1)

        else:
            raise NotImplementedError(f"Not Impl class decl {child.kind}")

    CursorState.all_simobjs.append(simobj)

class CursorState:
    cursor = None
    simobj = None
    flowpath = None
    actspath = None
    namespace = ':'
    prev_stack = []

    global_simobj = SimObjInfo('global', ':')
    all_actspaths = []
    all_simobjs = [global_simobj]

    @staticmethod
    def clear():
        CursorState.cursor = None
        CursorState.simobj = None
        CursorState.flowpath = None
        CursorState.actspath = None
        CursorState.namespace = ':'
        CursorState.prev_stack.clear()

def handle_funct_decl(cursor, scope):
    flowp = SimFlowPath(cursor.spelling)
    actsp = ActionFlow(cursor.spelling)
    actsp.add_block(HEAD_BLOCK)

    for child in cursor.get_children():
        if   child.kind == CursorKind.TYPE_REF:
            flowp.field = child.type.spelling
        
        elif child.kind == CursorKind.PARM_DECL:
            print(f'++ Insert Param: {child.spelling}, type: {child.type.spelling}')
            if check_gem5_class(child.type.spelling):
                print(Fore.GREEN + f'Gem5 Class: {child.type.spelling}, Detected', Fore.RESET)
            
            flowp.insert(
                SimVarNode( child.spelling, 
                            child.type, 
                            None ),
                is_input = True)

        elif child.kind == CursorKind.COMPOUND_STMT:
            CursorState.flowpath = flowp
            CursorState.actspath = actsp
            actsp.add_block(EXEC_BLOCK)
            handle_stmt(child, scope)
    
    CursorState.all_actspaths.append(actsp)
    actsp.print_flow()
    CursorState.actspath = None

def handle_decl(cursor, scope):
    display_info(cursor, scope)

    if cursor.kind in [CursorKind.VAR_DECL,
                       CursorKind.FIELD_DECL]:
        children = cursor.get_children()

        init = next(children, None)
        init = handle_expr(init, scope + 1) if init else None
        node = SimVarNode(  cursor.spelling, 
                            cursor.type, 
                            init )

        if cursor.kind == CursorKind.FIELD_DECL:
            if CursorState.simobj is None:
                raise RuntimeError(f"SimObj Not found")
            CursorState.simobj.insert_field(node)

        elif cursor.kind == CursorKind.VAR_DECL:
            if CursorState.flowpath is None:
                raise RuntimeError(f"Flowpath Not found")
            CursorState.flowpath.insert(node)
            CursorState.actspath.add_stmt(node)
        
    elif cursor.kind == CursorKind.CLASS_DECL:
        handle_class_decl(cursor, scope)

    elif cursor.kind == CursorKind.CONSTRUCTOR:
        print(Fore.RED + '!WARNING: Constructor Not Implemented', Fore.RESET)

    elif cursor.kind == CursorKind.CXX_METHOD:
        if not cursor.is_definition():
            return
        
        if check_gem5_api(cursor.spelling):
            print(Fore.GREEN + f'Gem5 API: {cursor.spelling}, Detected', Fore.RESET)
            return
        
        handle_funct_decl(cursor, scope)
        CursorState.simobj.insert_path(CursorState.flowpath)

    elif cursor.kind == CursorKind.FUNCTION_DECL:
        if not cursor.is_definition():
            return
        
        handle_funct_decl(cursor, scope)
        CursorState.global_simobj.insert_path(CursorState.flowpath)

    else :
        raise NotImplementedError(f"Not Impl decl {cursor.kind}")


def handle_expr(cursor, scope) -> BaseNode:
    display_info(cursor, scope)

    if cursor.kind == CursorKind.UNEXPOSED_EXPR:
        return handle_expr(next(cursor.get_children()), scope+1)
    
    elif cursor.kind == CursorKind.UNARY_OPERATOR:
        children = cursor.get_children()
        oprand = list(cursor.get_tokens())[0]
        s_node = handle_expr(next(children), scope + 1)
        print(f"    ++ Unary Oprand: {oprand.spelling}")

        return UryOpNode(oprand.spelling, s_node)

    elif cursor.kind == CursorKind.BINARY_OPERATOR:
        children = cursor.get_children()
        oprand = list(cursor.get_tokens())[1]
        l_node = handle_expr(next(children), scope + 1)
        r_node = handle_expr(next(children), scope + 1)

        if oprand.spelling == '=':
            l_node.add_relation(r_node)
        
        return BinOpNode(oprand.spelling, l_node, r_node)

    elif cursor.kind == CursorKind.PAREN_EXPR:
        return handle_expr(next(cursor.get_children()), scope + 1)
    
    elif cursor.kind == CursorKind.CALL_EXPR:
        children = cursor.get_children()
        callee = next(children)
        args = [handle_expr(arg, scope + 1) for arg in children]

        return SimFuncBox(callee.spelling, args)

    elif cursor.kind in [CursorKind.DECL_REF_EXPR,
                         CursorKind.MEMBER_REF_EXPR]:
        referent = cursor.get_definition()
        if not referent:
            raise RuntimeError(f"Definition Not found")
        
        if referent.kind in [CursorKind.VAR_DECL,
                             CursorKind.PARM_DECL]:    
            node = CursorState.flowpath.get(referent.spelling)
        
        elif referent.kind == CursorKind.FIELD_DECL:
            node = CursorState.simobj.get_field(referent.spelling)
        
        else:
            raise NotImplementedError(f"Not Impl decl ref expr {referent.kind}")
        
        if not node:
            raise RuntimeError(f"Node Not found")

        return node

    # handle literals
    elif cursor.kind in [CursorKind.INTEGER_LITERAL, 
                         CursorKind.FLOATING_LITERAL, 
                         CursorKind.IMAGINARY_LITERAL, 
                         CursorKind.STRING_LITERAL, 
                         CursorKind.CHARACTER_LITERAL, 
                         CursorKind.CXX_BOOL_LITERAL_EXPR, 
                         CursorKind.CXX_NULL_PTR_LITERAL_EXPR]:
        lit = list(cursor.get_tokens())[0]
        return LitNode(cursor.kind.name, lit)

    else :
        raise NotImplementedError(f"Not Impl expr {cursor.kind}")
    

def handle_stmt(cursor, scope):
    display_info(cursor, scope)

    if cursor.kind == CursorKind.COMPOUND_STMT:
        for child in cursor.get_children():
            handle_stmt(child, scope + 1)

    elif cursor.kind.is_expression():
        expr = handle_expr(cursor, scope)
        CursorState.actspath.add_stmt(expr)

    elif cursor.kind == CursorKind.IF_STMT:
        children = cursor.get_children()
        condition = next(children, None)
        then_stmt = next(children, None)
        else_stmt = next(children, None)
        # handle condition expression
        cond = handle_expr(condition, scope + 1)
        CursorState.actspath.add_block(BRANCH_BLOCK, cond)

        if then_stmt:
            print('>>>Then Stmt>>>')
            CursorState.actspath.add_branch(EXEC_BLOCK)
            handle_stmt(then_stmt, scope + 1)
            CursorState.actspath.ret_branch()

        if else_stmt:
            print('>>>Else Stmt>>>')
            CursorState.actspath.add_branch(EXEC_BLOCK)
            handle_stmt(else_stmt, scope + 1)
            CursorState.actspath.ret_branch()
        
        CursorState.actspath.pop_branch()

    elif cursor.kind == CursorKind.FOR_STMT:
        raise NotImplementedError(f"Not Impl for stmt {cursor.kind}")

    elif cursor.kind == CursorKind.DECL_STMT:
        children = cursor.get_children()
        handle_decl(next(children), scope)

    elif cursor.kind == CursorKind.RETURN_STMT:
        children = cursor.get_children()
        print('>>>Return Stmt>>>')
        ret = handle_expr(next(children), scope + 1)
        print(f"    >Return: {ret.name}")
        CursorState.flowpath.insert(ret, is_ouput = True)
        CursorState.actspath.add_stmt(ret)

    else:
        print_tokens(cursor)
        raise NotImplementedError(f"Not Impl stmt {cursor.kind}, is_decl? {cursor.kind.is_declaration()}, is_stmt? {cursor.kind.is_statement()},is_expr? {cursor.kind.is_expression()}")

def travel_code(cursor, filename,scope):
    # display_info(cursor, scope)
    # print(f'    is_define? {cursor.is_definition()}, \
    #         is_decl? {cursor.kind.is_declaration()}, \
    #         is_expr? {cursor.kind.is_expression( )},')
    
    if cursor.kind == CursorKind.TRANSLATION_UNIT:
        for child in cursor.get_children():
            if child.location.file.name == filename:
                travel_code(child,filename, scope)

    elif cursor.kind == CursorKind.NAMESPACE:
        print(f'>>>Namespace:  {cursor.spelling}>>>')
        CursorState.namespace = cursor.spelling + ':'

        for child in cursor.get_children():
            travel_code(child,filename, scope)

    elif cursor.kind.is_declaration():
        handle_decl(cursor, scope)

    elif cursor.kind.is_statement():
        handle_stmt(cursor, scope)

    # for child in cursor.get_children():
    #     travel_code(child, scope)
    else :
        raise NotImplementedError(f"Not Impl {cursor.kind}")

    return


source_code = '/workspaces/gem5-stable/gpower/test/cxxmethod.cc'
# source_code = "/workspaces/gem5-stable/src/learning_gem5/part2/simple_cache.cc"
args = ['-fsyntax-only', '-I' ,'/workspaces/gem5-stable/src/']

source_code = remove_gem5_macro(source_code)
#save file
with open('gpower/main.cc', 'w') as f:
    f.write(source_code)

# tu = index.parse(source_code, args=args)
tu = index.parse("main.cc", unsaved_files=[("main.cc", source_code)], args=args)
# print_diagnostic_info(tu)

CursorState.clear()
travel_code(tu.cursor, "main.cc", 0)