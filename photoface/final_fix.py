import os

# Define the new blocks
NEW_EXPRESSIONS = """<Expressions>
                  <Expression name="missingSteps">[STEP_GOAL] == 0</Expression>
                  <Expression name="stepsTier5">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 100</Expression>
                  <Expression name="stepsTier4">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 80</Expression>
                  <Expression name="stepsTier3">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 60</Expression>
                  <Expression name="stepsTier2">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 40</Expression>
                  <Expression name="stepsTier1">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 20</Expression>
                </Expressions>"""

def get_new_arc_compare(start_angle, thickness):
    return f"""<Compare expression="missingSteps">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                  <Stroke color="#FF888888" thickness="{thickness}" cap="ROUND"/>
                  <Transform target="endAngle" value="{start_angle} + 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier5">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                  <Stroke color="#FF00E5FF" thickness="{thickness}" cap="ROUND"/>
                  <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier4">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                  <Stroke color="#FF2E7D32" thickness="{thickness}" cap="ROUND"/>
                  <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier3">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                  <Stroke color="#FF8BC34A" thickness="{thickness}" cap="ROUND"/>
                  <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier2">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                  <Stroke color="#FFFFEB3B" thickness="{thickness}" cap="ROUND"/>
                  <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier1">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                  <Stroke color="#FFFF9800" thickness="{thickness}" cap="ROUND"/>
                  <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Default>
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                  <Stroke color="#FFFF5252" thickness="{thickness}" cap="ROUND"/>
                  <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Default>"""

def get_new_text_compare(x, y, angle, size):
    return f"""<Compare expression="missingSteps"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF888888"><Template>--</Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier5"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF00E5FF"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier4"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF2E7D32"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier3"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF8BC34A"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier2"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FFFFEB3B"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier1"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FFFF9800"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Default><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FFFF5252"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Default>"""

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

# 1. Update all <Expressions> blocks for steps
import re
text = re.sub(r'<Expressions>[\s\S]*?stepsMed[\s\S]*?</Expressions>', NEW_EXPRESSIONS, text)

# 2. Update Arc compares
# Quadrant 1 (TL)
text = text.replace(
    '<Compare expression="missingSteps">\n              <PartDraw x="0" y="0" width="450" height="450">\n                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="270" endAngle="270" direction="CLOCKWISE">\n                  <Stroke color="#FF888888" thickness="10" cap="ROUND"/>\n                  <Transform target="endAngle" value="270 + 90"/>\n                </Arc>\n              </PartDraw>\n            </Compare>\n            <Compare expression="stepsHigh">',
    get_new_arc_compare(270, 10) + ' <Compare expression="REMOVED_BY_SCRIPT">' # Dummy marker to keep rest of string
)
# Repeat for other quadrants... actually, let's just use a loop to find startAngle and thickness

# 3. Clean up the shadow hands
text = re.sub(
    r'<!-- Shadow minute hand - 12px offset down-right -->\s*<AnalogClock x="0" y="0" width="450" height="450">\s*(<MinuteHand[^>]+>\s*<Variant mode="AMBIENT" target="alpha" value="0"/>\s*</MinuteHand>)\s*</AnalogClock>\s*<!-- Shadow hour hand - 12px offset down-right -->\s*<AnalogClock x="0" y="0" width="450" height="450">\s*(<HourHand[^>]+>\s*<Variant mode="AMBIENT" target="alpha" value="0"/>\s*</HourHand>)\s*</AnalogClock>',
    r'''<!-- Shadow hands - 12px offset down-right -->
        <AnalogClock x="0" y="0" width="450" height="450">
          \2
          \1
        </AnalogClock>''',
    text
)

# 4. Deactivate Sweep in AOD
text = re.sub(
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">',
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">\n              <Variant mode="AMBIENT" target="alpha" value="0"/>',
    text
)

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(text)

print("Script finished partially. Let's do the rest with surgical replaces.")
