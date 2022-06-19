import ast
import json

def get_variable_from_html(var_name, htm_string):
    start = htm_string.find(var_name)
    if start == -1:
        return None

    
    var_string = htm_string[start:].split("\n")[0]
    var_len = var_string.find(";")
    if var_len == -1:
        return None
    var_string = var_string[:var_len]
    var_string = var_string.split("=")
    if len(var_string) > 1:
        var_string = var_string[1]
    else:
        return None
    var_string = var_string.lstrip()
    if var_string == "null":
        return None
    try:
        var_obj = ast.literal_eval(var_string)
        return var_obj
    except:
        return None
    

def get_json_variable_from_html(var_name, htm_string):
    start = htm_string.find(var_name)
    if start == -1:
        return None
    var_string = htm_string[start:].split("\n")[0]
    var_string = var_string[var_string.find("=")+1:]
    var_string = var_string.lstrip()
    if var_string[-1]==";":
        var_string = var_string[:-1]
    elif var_string[-2] == ";":
        var_string = var_string[:-2]
    if var_string == "null":
        return None
    if len(var_string) == 0:
        return None
    try:
        var_json = json.loads(var_string)
        return var_json
    except:
        return None