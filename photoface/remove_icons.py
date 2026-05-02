import re

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    content = f.read()

# Find the UserConfigurations block
start_tag = '<UserConfigurations>'
end_tag = '</UserConfigurations>'
start_idx = content.find(start_tag)
end_idx = content.find(end_tag)

if start_idx != -1 and end_idx != -1:
    user_configs = content[start_idx:end_idx]
    
    # We want to remove `icon="@drawable/..."` from ListConfiguration and ListOption elements.
    # The regex \s*icon="[^"]+" matches the attribute and preceding whitespace.
    updated_configs = re.sub(r'\s*icon="[^"]+"', '', user_configs)
    
    # Reassemble the file content
    new_content = content[:start_idx] + updated_configs + content[end_idx:]
    
    with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
        f.write(new_content)
    print("Successfully removed icons from UserConfigurations.")
else:
    print("Could not find UserConfigurations block.")
