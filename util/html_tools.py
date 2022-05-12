import ast
import json

def get_variable_from_html(var_name, htm_string):
    start = htm_string.find(var_name)
    len = htm_string[start:].find(";")
    var_string = htm_string[start:start+len]
    var_string = var_string.split("=")[1]
    var_string = var_string.lstrip()
    if var_string == "null":
        return []
    var_obj = ast.literal_eval(var_string)
    return var_obj

def get_json_variable_from_html(var_name, htm_string):
    start = htm_string.find(var_name)
    var_string = htm_string[start:].split("\n")[0]
    var_string = var_string.split("=")[1]
    var_string = var_string.lstrip()
    if var_string[-1]==";":
        var_string = var_string[:-1]
    elif var_string[-2] == ";":
        var_string = var_string[:-2]
    if var_string == "null":
        return {}
    return json.loads(var_string)