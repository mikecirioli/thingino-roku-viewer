import re

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

# Replace any number of Variant tags that follow AnalogClock secondsPerCycle="60">
text = re.sub(
    r'(<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">)(?:\s*<Variant mode="AMBIENT" target="alpha" value="0"/>)+',
    r'\1',
    text
)

# Also remove Variant inside AnalogClock for the shadow hands just in case they were added
text = re.sub(
    r'(<AnalogClock x="0" y="0" width="450" height="450">)(?:\s*<Variant mode="AMBIENT" target="alpha" value="0"/>)+',
    r'\1',
    text
)

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(text)
