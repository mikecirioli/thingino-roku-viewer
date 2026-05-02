import re

# I will verify the xml syntax. 
# `<PhotosConfiguration id="bgPhoto" configType="MULTIPLE" displayName="@string/bg_photo" />` is exactly what the documentation says.
# But sometimes, missing `screenReaderText` can cause it to be hidden. Let's add it.

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

text = text.replace(
    '<PhotosConfiguration id="bgPhoto" configType="MULTIPLE" displayName="@string/bg_photo" />',
    '<PhotosConfiguration id="bgPhoto" configType="MULTIPLE" displayName="@string/bg_photo" screenReaderText="@string/bg_photo" />'
)

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(text)
