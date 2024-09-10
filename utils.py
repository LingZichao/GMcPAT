import re
from colorama import Fore, Style

def print_tokens(cursor) :
    token_list = cursor.get_tokens()
    for tk in token_list :
        print(f"    >Token: {tk.spelling} ({tk.kind}) at line {tk.location.line}, column {tk.location.column}")

def print_children_cnt(cursor) :
    print(f"    >Children: {len(list(cursor.get_children()))}")

def is_leaf(cursor) :
    return not list(cursor.get_children())

def remove_std_include(filepath) :
    with open(filepath, 'r') as file:
        source = file.read()

    pattern = r'^\s*#\s*include\s*<[^>]+>'
    filtered = re.sub(pattern, '', source, flags=re.MULTILINE)

    return filtered

def remove_gem5_macro(filepath) :
    with open(filepath, 'r') as file:
        source = file.read()

    # remove panic_if();
    pattern = r'^\s*panic_if\s*\([\s\S]*?\);'
    filtered = re.sub(pattern, '', source, flags=re.MULTILINE)

    # remove panic();
    pattern = r'^\s*panic\s*\([\s\S]*?\);'
    filtered = re.sub(pattern, '', filtered, flags=re.MULTILINE)

    # remove DPRINTF();
    pattern = r'^\s*DPRINTF\s*\([\s\S]*?\);'
    filtered = re.sub(pattern, '', filtered, flags=re.MULTILINE)

    # remove assert();
    pattern = r'^\s*assert\s*\([\s\S]*?\);'
    filtered = re.sub(pattern, '', filtered, flags=re.MULTILINE)
    return filtered


def print_diagnostic_info(tu):
    for diag in tu.diagnostics:
        print(f"错误类型: {diag.severity}")
        print(f"错误位置: {diag.location.file}:{diag.location.line}:{diag.location.column}")
        print(f"错误信息: {diag.spelling}")

def display_info(cursor, scope = 0, show_file_path = False):
    print(Fore.BLUE + f"{'-'*scope}"+
          f"Name: {cursor.spelling},"+
          f"Kind: {cursor.kind}, "+
          f"Full: {cursor.displayname}, "+
          f"Type: {cursor.type.spelling}, "+
          (f"File path: {cursor.location.file}, " if show_file_path else "") 
          
          + Fore.RESET)
