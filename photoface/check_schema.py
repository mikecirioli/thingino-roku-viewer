import urllib.request
import re

url = "https://raw.githubusercontent.com/google/watchface/main/schema/watchface.xsd"
try:
    req = urllib.request.urlopen(url)
    xsd_content = req.read().decode('utf-8')
    print("Downloaded Schema.")
    matches = re.findall(r'<xs:element name="PhotosConfiguration"[\s\S]*?</xs:element>', xsd_content)
    if matches:
        print(matches[0])
    else:
        print("PhotosConfiguration not found in schema.")
except Exception as e:
    print(f"Error: {e}")
