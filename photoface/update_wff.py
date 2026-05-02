import re

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

# 1. Add missingSteps expression to all Steps conditions
text = re.sub(
    r'(<Expression name="stepsHigh">)',
    r'<Expression name="missingSteps">[STEP_GOAL] == 0</Expression>\n              \1',
    text
)

# 2. Add missingSteps Compare to all Steps Arcs
# The pattern we need to find is where `<Compare expression="stepsHigh">` follows the `</Expressions>`
# and we need to inject the `missingSteps` compare block.
# We have to be careful with startAngle/endAngle because they vary per quadrant.
def replace_arc_compare(match):
    original_compare = match.group(0)
    # Extract the startAngle from the Arc element inside the stepsHigh Compare block
    start_angle_match = re.search(r'startAngle="(\d+)"', original_compare)
    if not start_angle_match:
        return original_compare
    start_angle = start_angle_match.group(1)
    
    missing_compare = f"""<Compare expression="missingSteps">
              <PartDraw x="0" y="0" width="450" height="450">
                <Arc centerX="225" centerY="225" width="430" height="430" startAngle="{start_angle}" endAngle="{start_angle}" direction="CLOCKWISE">
                  <Stroke color="#FF888888" thickness="10" cap="ROUND"/>
                  <Transform target="endAngle" value="{start_angle} + 90"/>
                </Arc>
              </PartDraw>
            </Compare>
            """
    return missing_compare + original_compare

text = re.sub(
    r'<Compare expression="stepsHigh">\s*<PartDraw[\s\S]*?</Compare>',
    replace_arc_compare,
    text
)

# 3. Add missingSteps Compare to all Steps Text (labelSize)
def replace_text_compare(match):
    original_compare = match.group(0)
    # We extract x, y, angle, size
    x_match = re.search(r'x="([^"]+)"', original_compare)
    y_match = re.search(r'y="([^"]+)"', original_compare)
    angle_match = re.search(r'angle="([^"]+)"', original_compare)
    size_match = re.search(r'size="([^"]+)"', original_compare)
    
    if not (x_match and y_match and angle_match and size_match):
        return original_compare
        
    x = x_match.group(1)
    y = y_match.group(1)
    angle = angle_match.group(1)
    size = size_match.group(1)
    
    missing_compare = f"""<Compare expression="missingSteps"><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF888888"><Template>--</Template></Font></Text></PartText></Compare>\n                """
    return missing_compare + original_compare

text = re.sub(
    r'<Compare expression="stepsHigh"><PartText.*?<\/Compare>',
    replace_text_compare,
    text
)

# For Heart Rate:
# HR arc thickness options don't use Condition expressions right now, they just use <Transform target="endAngle" value="... clamp(([HEART_RATE] - 40) / 160, 0, 1) * 90" />
# If we wrap it in a Condition, it'll require rewriting the entire HR ListOption blocks which is huge.
# Alternatively, we can just replace `([HEART_RATE] - 40) / 160` with `([HEART_RATE] > 0 ? ([HEART_RATE] - 40) / 160 : 0)`
# Wait, WFF expressions don't support ternary operator `? :`.
# Since WFF handles `[HEART_RATE]` cleanly by substituting 0 when missing, and clamp((0-40)/160, 0, 1) is clamp(-0.25, 0, 1) = 0.
# So the arc will end up being length 0. This is ALREADY an implicit graceful degradation (no arc shown).
# The only issue is the text shows `0`. We can fix the HR text.
# The HR text looks like:
# <ListOption id="0"><PartText ...><Text align="CENTER"><Font ... color="[CONFIGURATION.heartColor]"><Template>%d<Parameter expression="[HEART_RATE]"/></Template></Font></Text></PartText></ListOption>
# Let's wrap each PartText inside a Condition to check `[HEART_RATE] > 0`

def replace_hr_text(match):
    original_option = match.group(0)
    inner_parttext = match.group(1)
    
    # We want to replace the `Template` part with `--` if `[HEART_RATE] == 0`
    # We can do this by wrapping the inner PartText inside a `<Condition>`
    
    # Extract PartText attributes: x, y, angle, size
    x_m = re.search(r'x="([^"]+)"', inner_parttext)
    y_m = re.search(r'y="([^"]+)"', inner_parttext)
    angle_m = re.search(r'angle="([^"]+)"', inner_parttext)
    size_m = re.search(r'size="([^"]+)"', inner_parttext)
    
    x = x_m.group(1) if x_m else "0"
    y = y_m.group(1) if y_m else "0"
    angle = angle_m.group(1) if angle_m else "0"
    size = size_m.group(1) if size_m else "16"
    
    # original inner_parttext has the %d formatting
    
    condition_block = f"""<Condition>
              <Expressions><Expression name="hasHR">[HEART_RATE] > 0</Expression></Expressions>
              <Compare expression="hasHR">{inner_parttext}</Compare>
              <Default><PartText x="{x}" y="{y}" width="70" height="35" pivotX="0.5" pivotY="0.5" angle="{angle}"><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="{size}" weight="BOLD" color="#FF888888"><Template>--</Template></Font></Text></PartText></Default>
            </Condition>"""
            
    # Need to keep the <ListOption id="X"> wrapper
    list_option_start = re.search(r'<ListOption id="\d+">', original_option).group(0)
    return f"{list_option_start}{condition_block}</ListOption>"

text = re.sub(
    r'<ListOption id="\d+">(<PartText [^>]+><Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="\d+" weight="BOLD" color="\[CONFIGURATION.heartColor\]"><Template>%d<Parameter expression="\[HEART_RATE\]"\/>.*?<\/PartText>)<\/ListOption>',
    replace_hr_text,
    text
)

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(text)

