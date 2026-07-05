import sys
import json
import re

def parse_pseudo_schema(schema_text):
    schema = {}
    lines = schema_text.strip().split('\n')
    for line in lines:
        line = line.split('#')[0].strip()
        if not line or line in ('{', '}'):
            continue
        
        # Handle "...original fields..."
        if "..." in line:
            continue
            
        match = re.match(r'"([^"]+)"\s*:\s*(.+),?', line)
        if match:
            field, type_str = match.groups()
            type_str = type_str.rstrip(',')
            schema[field] = type_str.strip()
    return schema

def validate_field(value, type_str):
    if type_str == 'str':
        return isinstance(value, str)
    elif type_str == 'int':
        return isinstance(value, int) and not isinstance(value, bool)
    elif type_str == 'float':
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    elif type_str == 'bool':
        return isinstance(value, bool)
    elif type_str == '[str]':
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    elif type_str == 'str | null':
        return value is None or isinstance(value, str)
    return True # fallback for unknown types

def main():
    if len(sys.argv) != 3:
        print("Usage: python validate.py <json_sample> <schema_ref>")
        sys.exit(1)
        
    json_path = sys.argv[1]
    schema_path = sys.argv[2]
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        sys.exit(1)
        
    try:
        with open(schema_path, 'r') as f:
            schema_text = f.read()
    except Exception as e:
        print(f"Error loading schema: {e}")
        sys.exit(1)
        
    schema = parse_pseudo_schema(schema_text)
    
    errors = []
    
    # Check if data is a list (e.g. per posting), but schema is usually per item.
    # If it's a list, validate the first item or all items. Let's just validate it as a dict.
    items_to_validate = data if isinstance(data, list) else [data]
    
    for idx, item in enumerate(items_to_validate):
        for field, type_str in schema.items():
            if field not in item:
                errors.append(f"Item {idx}: Missing required field '{field}'")
            else:
                if not validate_field(item[field], type_str):
                    errors.append(f"Item {idx}: Field '{field}' expected type {type_str}, got {type(item[field]).__name__}")
                    
    if errors:
        print("Validation Failed:")
        for err in errors:
            print(f"- {err}")
        sys.exit(1)
    else:
        print("PASS")
        sys.exit(0)

if __name__ == '__main__':
    main()
