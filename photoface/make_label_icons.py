import os

# Let's create vector drawables that contain the actual text letters!
# We will overwrite the abstract dots (ic_label_small.png etc) with text vectors.

# ic_label_small.xml
small_xml = '''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FFFFFF"
        android:pathData="M12,17 L9,17 L10.5,12 L13.5,12 Z M10.5,9 L13.5,9 L17,19 L14,19 L13.2,16 L10.8,16 L10,19 L7,19 L10.5,9 Z"/>
</vector>'''

# Since we don't have a good font renderer in VectorDrawable, we can just make simple path representations of 'A', but doing that cleanly via regex path data is tedious.
# Alternative: I can use ImageMagick or standard text if ImageMagick is installed, but since I am a script I can just use a generic 'A' path and scale it!

A_path = "M10.5,9 L13.5,9 L17,19 L14,19 L13.2,16 L10.8,16 L10,19 L7,19 L10.5,9 Z M11.5,13.5 L12.5,13.5 L12,11.5 Z"

def make_vector(scale, offset_y):
    # Scale the path manually or just use android:scaleX in a group
    return f'''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <group android:scaleX="{scale}" android:scaleY="{scale}" android:pivotX="12" android:pivotY="12" android:translateY="{offset_y}">
        <path android:fillColor="#FFFFFF" android:pathData="{A_path}"/>
    </group>
</vector>'''

os.makedirs('watchface/src/main/res/drawable', exist_ok=True)

with open('watchface/src/main/res/drawable/ic_label_small.xml', 'w') as f:
    f.write(make_vector(0.6, 2))
with open('watchface/src/main/res/drawable/ic_label_medium.xml', 'w') as f:
    f.write(make_vector(0.8, 1))
with open('watchface/src/main/res/drawable/ic_label_large.xml', 'w') as f:
    f.write(make_vector(1.0, 0))
with open('watchface/src/main/res/drawable/ic_label_xlarge.xml', 'w') as f:
    f.write(make_vector(1.3, -1))

# Now update watchface.xml to point to the .xml instead of .png
