import re

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

# Remove the invalid Variant tags injected right after AnalogClock
text = re.sub(
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">\s*<Variant mode="AMBIENT" target="alpha" value="0"/>\s*<Variant mode="AMBIENT" target="alpha" value="0"/>',
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">',
    text
)
# Just in case there's only one
text = re.sub(
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">\s*<Variant mode="AMBIENT" target="alpha" value="0"/>',
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">',
    text
)

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(text)
