import re

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

# 1. FIX PHOTOS PICKER (Add displayName)
text = re.sub(
    r'<PhotosConfiguration id="bgPhoto" configType="MULTIPLE" />',
    r'<PhotosConfiguration id="bgPhoto" configType="MULTIPLE" displayName="Background" />',
    text
)

# 2. OPTIMIZE AOD (Shadow Hand Consolidation)
# Combine the two separate shadow AnalogClocks into one.
text = re.sub(
    r'<!-- Shadow minute hand - 12px offset down-right -->\s*<AnalogClock x="0" y="0" width="450" height="450">\s*(<MinuteHand[^>]+>\s*<Variant mode="AMBIENT" target="alpha" value="0"/>\s*</MinuteHand>)\s*</AnalogClock>\s*<!-- Shadow hour hand - 12px offset down-right -->\s*<AnalogClock x="0" y="0" width="450" height="450">\s*(<HourHand[^>]+>\s*<Variant mode="AMBIENT" target="alpha" value="0"/>\s*</HourHand>)\s*</AnalogClock>',
    r'''<!-- Shadow hands - 12px offset down-right -->
        <AnalogClock x="0" y="0" width="450" height="450">
          \2
          \1
        </AnalogClock>''',
    text
)

# Deactivate Sweep in AOD
text = re.sub(
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">',
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">\n              <Variant mode="AMBIENT" target="alpha" value="0"/>',
    text
)

# 3. IMPLEMENT 6-TIER STEP COLORS
# Replace the Expressions
text = re.sub(
    r'<Expressions>\s*<Expression name="stepsHigh">\(\[STEP_COUNT\] \* 100 / \[STEP_GOAL\]\) >= 75</Expression>\s*<Expression name="stepsMedHigh">\(\[STEP_COUNT\] \* 100 / \[STEP_GOAL\]\) >= 50</Expression>\s*<Expression name="stepsMed">\(\[STEP_COUNT\] \* 100 / \[STEP_GOAL\]\) >= 25</Expression>\s*</Expressions>',
    r'''<Expressions>
                  <Expression name="missingSteps">[STEP_GOAL] == 0</Expression>
                  <Expression name="stepsTier5">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 100</Expression>
                  <Expression name="stepsTier4">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 80</Expression>
                  <Expression name="stepsTier3">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 60</Expression>
                  <Expression name="stepsTier2">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 40</Expression>
                  <Expression name="stepsTier1">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 20</Expression>
                </Expressions>''',
    text
)

# Replace the Arcs and Text
# We'll do this by targeting the specific patterns.
def fix_steps(content):
    # This is a bit brute force but safe for the repeating blocks
    
    # 6-tier Arc Compare block
    new_arc_compares = '''<Compare expression="missingSteps">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{angle}" endAngle="{angle}" direction="CLOCKWISE">
                  <Stroke color="#FF888888" thickness="{thick}" cap="ROUND"/>
                  <Transform target="endAngle" value="{angle} + 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier5">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{angle}" endAngle="{angle}" direction="CLOCKWISE">
                  <Stroke color="#FF00E5FF" thickness="{thick}" cap="ROUND"/>
                  <Transform target="endAngle" value="{angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier4">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{angle}" endAngle="{angle}" direction="CLOCKWISE">
                  <Stroke color="#FF2E7D32" thickness="{thick}" cap="ROUND"/>
                  <Transform target="endAngle" value="{angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier3">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{angle}" endAngle="{angle}" direction="CLOCKWISE">
                  <Stroke color="#8BC34A" thickness="{thick}" cap="ROUND"/>
                  <Transform target="endAngle" value="{angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier2">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{angle}" endAngle="{angle}" direction="CLOCKWISE">
                  <Stroke color="#FFEB3B" thickness="{thick}" cap="ROUND"/>
                  <Transform target="endAngle" value="{angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Compare expression="stepsTier1">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{angle}" endAngle="{angle}" direction="CLOCKWISE">
                  <Stroke color="#FFFF9800" thickness="{thick}" cap="ROUND"/>
                  <Transform target="endAngle" value="{angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            <Default>
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{angle}" endAngle="{angle}" direction="CLOCKWISE">
                  <Stroke color="#FFF44336" thickness="{thick}" cap="ROUND"/>
                  <Transform target="endAngle" value="{angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                </Arc>
              </PartDraw>
            </Default>'''

    # 6-tier Text Compare block
    new_text_compares = '''<Compare expression="missingSteps"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF888888"><Template>--</Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier5"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF00E5FF"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier4"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF2E7D32"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier3"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#8BC34A"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier2"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FFEB3B"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier1"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FFFF9800"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Default><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FFF44336"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Default>'''

    # Since there are multiple quadrants and thicknesses, we'll just replace the core structures.
    # To keep it simple, I'll use re.sub with placeholders or just leave the complex regex out and do literal replacements for the known structures.
    
    return content

# I'll just re-run the previous script logic but better.
# Actually, I'll just do a clean fix for the Photos picker first.

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(text)
