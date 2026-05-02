import re

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

# 1. FIX PHOTOS PICKER (Add displayName)
# This is likely why it's missing from the menu.
text = re.sub(
    r'<PhotosConfiguration id="bgPhoto" configType="MULTIPLE" />',
    r'<PhotosConfiguration id="bgPhoto" configType="MULTIPLE" displayName="Background" />',
    text
)

# 2. OPTIMIZE AOD (Shadow Hand Consolidation)
# Combine the two separate shadow AnalogClocks into one to save memory.
text = re.sub(
    r'<!-- Shadow minute hand - 12px offset down-right -->\s*<AnalogClock x="0" y="0" width="450" height="450">\s*(<MinuteHand[^>]+>\s*<Variant mode="AMBIENT" target="alpha" value="0"/>\s*</MinuteHand>)\s*</AnalogClock>\s*<!-- Shadow hour hand - 12px offset down-right -->\s*<AnalogClock x="0" y="0" width="450" height="450">\s*(<HourHand[^>]+>\s*<Variant mode="AMBIENT" target="alpha" value="0"/>\s*</HourHand>)\s*</AnalogClock>',
    r'''<!-- Shadow hands - 12px offset down-right -->
        <AnalogClock x="0" y="0" width="450" height="450">
          \2
          \1
        </AnalogClock>''',
    text, flags=re.MULTILINE
)

# Deactivate Sweep ticks in AOD
text = re.sub(
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">',
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">\n              <Variant mode="AMBIENT" target="alpha" value="0"/>',
    text
)

# 3. IMPLEMENT 6-TIER STEP COLORS
# Update the Expressions block
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
    text, flags=re.MULTILINE
)

# Replacement logic for Arcs (Iterate through all 4 quadrants)
def fix_arc_block(match_text):
    # Extract startAngle and thickness from the existing code
    start_angle = re.search(r'startAngle="(\d+)"', match_text).group(1)
    thickness = re.search(r'thickness="(\d+)"', match_text).group(1)
    
    return f'''<Condition>
                <Expressions>
                  <Expression name="missingSteps">[STEP_GOAL] == 0</Expression>
                  <Expression name="stepsTier5">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 100</Expression>
                  <Expression name="stepsTier4">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 80</Expression>
                  <Expression name="stepsTier3">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 60</Expression>
                  <Expression name="stepsTier2">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 40</Expression>
                  <Expression name="stepsTier1">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 20</Expression>
                </Expressions>
                <Compare expression="missingSteps">
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
                  <PartDraw x="0" y="0" width="450" height="450" pivotX="0.5" pivotY="0.5">
                    <Ellipse x="215" y="3" width="20" height="20"><Fill color="#FFFFFFFF"/></Ellipse>
                    <Ellipse x="218" y="6" width="14" height="14"><Fill color="#FF00E5FF"/></Ellipse>
                    <Transform target="angle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                  </PartDraw>
                </Compare>
                <Compare expression="stepsTier4">
                  <PartDraw x="0" y="0" width="450" height="450">
                    <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                      <Stroke color="#FF2E7D32" thickness="{thickness}" cap="ROUND"/>
                      <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                    </Arc>
                  </PartDraw>
                  <PartDraw x="0" y="0" width="450" height="450" pivotX="0.5" pivotY="0.5">
                    <Ellipse x="215" y="3" width="20" height="20"><Fill color="#FFFFFFFF"/></Ellipse>
                    <Ellipse x="218" y="6" width="14" height="14"><Fill color="#FF2E7D32"/></Ellipse>
                    <Transform target="angle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                  </PartDraw>
                </Compare>
                <Compare expression="stepsTier3">
                  <PartDraw x="0" y="0" width="450" height="450">
                    <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                      <Stroke color="#8BC34A" thickness="{thickness}" cap="ROUND"/>
                      <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                    </Arc>
                  </PartDraw>
                  <PartDraw x="0" y="0" width="450" height="450" pivotX="0.5" pivotY="0.5">
                    <Ellipse x="215" y="3" width="20" height="20"><Fill color="#FFFFFFFF"/></Ellipse>
                    <Ellipse x="218" y="6" width="14" height="14"><Fill color="#8BC34A"/></Ellipse>
                    <Transform target="angle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                  </PartDraw>
                </Compare>
                <Compare expression="stepsTier2">
                  <PartDraw x="0" y="0" width="450" height="450">
                    <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                      <Stroke color="#FFEB3B" thickness="{thickness}" cap="ROUND"/>
                      <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                    </Arc>
                  </PartDraw>
                  <PartDraw x="0" y="0" width="450" height="450" pivotX="0.5" pivotY="0.5">
                    <Ellipse x="215" y="3" width="20" height="20"><Fill color="#FFFFFFFF"/></Ellipse>
                    <Ellipse x="218" y="6" width="14" height="14"><Fill color="#FFEB3B"/></Ellipse>
                    <Transform target="angle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                  </PartDraw>
                </Compare>
                <Compare expression="stepsTier1">
                  <PartDraw x="0" y="0" width="450" height="450">
                    <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                      <Stroke color="#FFFF9800" thickness="{thickness}" cap="ROUND"/>
                      <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                    </Arc>
                  </PartDraw>
                  <PartDraw x="0" y="0" width="450" height="450" pivotX="0.5" pivotY="0.5">
                    <Ellipse x="215" y="3" width="20" height="20"><Fill color="#FFFFFFFF"/></Ellipse>
                    <Ellipse x="218" y="6" width="14" height="14"><Fill color="#FFFF9800"/></Ellipse>
                    <Transform target="angle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                  </PartDraw>
                </Compare>
                <Default>
                  <PartDraw x="0" y="0" width="450" height="450">
                    <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                      <Stroke color="#FFF44336" thickness="{thickness}" cap="ROUND"/>
                      <Transform target="endAngle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                    </Arc>
                  </PartDraw>
                  <PartDraw x="0" y="0" width="450" height="450" pivotX="0.5" pivotY="0.5">
                    <Ellipse x="215" y="3" width="20" height="20"><Fill color="#FFFFFFFF"/></Ellipse>
                    <Ellipse x="218" y="6" width="14" height="14"><Fill color="#FFF44336"/></Ellipse>
                    <Transform target="angle" value="{start_angle} + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
                  </PartDraw>
                </Default>
              </Condition>'''

# Apply the arc replacement (Matches the Condition block for steps)
text = re.sub(r'<Condition>\s*<Expressions>.*?stepsMed.*?</Expressions>.*?<Compare expression="missingSteps">.*?</PartDraw>\s*</Default>\s*</Condition>', 
              lambda m: fix_arc_block(m.group(0)), 
              text, flags=re.DOTALL)

# Replacement logic for Text (Iterate through all labelSize options)
def fix_text_block(match_text):
    x = re.search(r'x="(\d+)"', match_text).group(1)
    y = re.search(r'y="(\d+)"', match_text).group(1)
    angle = re.search(r'angle="(-?\d+)"', match_text).group(1)
    size = re.search(r'size="(\d+)"', match_text).group(1)
    
    return f'''<Condition>
                <Expressions>
                  <Expression name="missingSteps">[STEP_GOAL] == 0</Expression>
                  <Expression name="stepsTier5">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 100</Expression>
                  <Expression name="stepsTier4">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 80</Expression>
                  <Expression name="stepsTier3">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 60</Expression>
                  <Expression name="stepsTier2">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 40</Expression>
                  <Expression name="stepsTier1">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 20</Expression>
                </Expressions>
                <Compare expression="missingSteps"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF888888"><Template>--</Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier5"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF00E5FF"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier4"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF2E7D32"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier3"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#8BC34A"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier2"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FFEB3B"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Compare expression="stepsTier1"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FFFF9800"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Compare>
                <Default><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FFF44336"><Template>%d<Parameter expression="[STEP_COUNT]"/></Template></Font></Text></PartText></Default>
              </Condition>'''

# Apply text replacement for Steps widgets inside labelSize
text = re.sub(r'<Compare expression="missingSteps"><PartText.*?/Default>', 
              lambda m: fix_text_block(m.group(0)), 
              text, flags=re.DOTALL)

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(text)
