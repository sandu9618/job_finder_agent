import sys
import os
import shutil

def main():
    if len(sys.argv) != 2:
        print("Usage: python scaffold_node.py <node_name>")
        sys.exit(1)
        
    node_name = sys.argv[1]
    
    if not node_name.isidentifier():
        print(f"Error: '{node_name}' is not a valid Python identifier.")
        sys.exit(1)
        
    workspace_root = os.getcwd()
    template_path = os.path.join(workspace_root, ".agents", "skills", "scaffold-graph-node", "references", "NodeTemplate.py")
    target_path = os.path.join(workspace_root, "job_finder_agent", "nodes", f"{node_name}.py")
    
    if not os.path.exists(template_path):
        print(f"Error: Template not found at {template_path}")
        sys.exit(1)
        
    if os.path.exists(target_path):
        print(f"Error: Target file {target_path} already exists.")
        sys.exit(1)
        
    with open(template_path, 'r') as f:
        content = f.read()
        
    # Replace TODO_NODE_NAME with the actual node name
    content = content.replace("TODO_NODE_NAME", node_name)
    
    with open(target_path, 'w') as f:
        f.write(content)
        
    print(target_path)

if __name__ == '__main__':
    main()
