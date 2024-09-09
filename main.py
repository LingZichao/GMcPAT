from clang.cindex import Config, Index, CursorKind

from utils import *
from ccsimobj import *

Config.set_library_file('/usr/lib/llvm-15/lib/libclang.so.1')
index = Index.create()


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
    namespace = ':'
    cond_stack = []
    prev_stack = []

    global_simobj = SimObjInfo('global', ':')
    all_simobjs = [global_simobj]

    @staticmethod
    def clear():
        CursorState.cursor = None
        CursorState.simobj = None
        CursorState.flowpath = None
        CursorState.namespace = ':'

        CursorState.cond_stack.clear()
        CursorState.prev_stack.clear()

def handle_funct_decl(cursor, scope):
    flowp = SimFlowPath(cursor.spelling)

    for child in cursor.get_children():
        if   child.kind == CursorKind.TYPE_REF:
            flowp.field = child.type.spelling
        
        elif child.kind == CursorKind.PARM_DECL:
            print(f'++Insert Param: {child.spelling}')
            flowp.insert(
                SimVarNode( child.spelling, 
                            child.type, 
                            None ),
                is_input = True)

        elif child.kind == CursorKind.COMPOUND_STMT:
            CursorState.flowpath = flowp
            handle_stmt(child, scope)

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
        
    elif cursor.kind == CursorKind.CLASS_DECL:
        handle_class_decl(cursor, scope)

    elif cursor.kind == CursorKind.CONSTRUCTOR:
        print('!WARNING: Constructor Not Implemented')

    elif cursor.kind == CursorKind.CXX_METHOD:
        if not cursor.is_definition():
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
        print(f"    >Oprand: {oprand.spelling}")
        s_node = handle_expr(next(children), scope + 1)

        return UryOpNode(oprand.spelling, s_node)

    elif cursor.kind == CursorKind.BINARY_OPERATOR:
        children = cursor.get_children()
        oprand = list(cursor.get_tokens())[1]
        l_node = handle_expr(next(children), scope + 1)
        r_node = handle_expr(next(children), scope + 1)

        if oprand.spelling == '=':
            l_node.add_relation(r_node)
        else :
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
                         CursorKind.CXX_NULL_PTR_LITERAL_EXPR,]:
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
        handle_expr(cursor, scope)

    elif cursor.kind == CursorKind.IF_STMT:
        children = cursor.get_children()
        condition = next(children, None)
        then_stmt = next(children, None)
        else_stmt = next(children, None)
        # handle condition expression
        handle_expr(condition, scope + 1)
        CursorState.cond_stack.append(condition)

        if then_stmt:
            print('>>>Then Stmt>>>')
            handle_stmt(then_stmt, scope + 1)

        if else_stmt:
            print('>>>Else Stmt>>>')
            handle_stmt(else_stmt, scope + 1)
        
        CursorState.cond_stack.pop()

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

    else:
        print_tokens(cursor)
        raise NotImplementedError(f"Not Impl stmt {cursor.kind}, is_decl? {cursor.kind.is_declaration()}, is_stmt? {cursor.kind.is_statement()},is_expr? {cursor.kind.is_expression()}")

# TODO : cursorstate的出入栈的问题

def travel_code(cursor, scope):
    display_info(cursor, scope)

    # print(f'    is_define? {cursor.is_definition()}, \
    #         is_decl? {cursor.kind.is_declaration()}, \
    #         is_expr? {cursor.kind.is_expression( )},')
    
    if cursor.kind == CursorKind.TRANSLATION_UNIT:
        for child in cursor.get_children():
            travel_code(child, scope)

    elif cursor.kind == CursorKind.NAMESPACE:
        print_children_cnt(cursor)
        print(f'>>>Namespace:  {cursor.spelling}>>>')
        CursorState.namespace = cursor.spelling + ':'

    elif cursor.kind.is_declaration():
        handle_decl(cursor, scope)

    elif cursor.kind.is_statement():
        handle_stmt(cursor, scope)

    # for child in cursor.get_children():
    #     travel_code(child, scope)
    else :
        raise NotImplementedError(f"Not Impl {cursor.kind}")

    return


# source_code = remove_std_include('/workspaces/gem5-stable/gpower/test/simple_cache.cc')
# print(source_code)
tu = index.parse("/workspaces/gem5-stable/gpower/test/simple_cache.cc", args=['-fsyntax-only'])
# tu = index.parse("main.cc", unsaved_files=[("main.cc", source_code)], args=['-fsyntax-only'])
print_diagnostic_info(tu)

CursorState.clear()

travel_code(tu.cursor, 0)