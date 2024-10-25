def is_dict_or_list_of_dicts(value):
    if isinstance(value, dict):
        return True
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return True
    return False
