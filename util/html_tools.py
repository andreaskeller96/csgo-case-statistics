import ast

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