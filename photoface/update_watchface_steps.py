import re

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

# 1. OPTIMIZE AOD
# The codebase investigator noted that there are 3 AnalogClocks instantiated per hand style.
# <AnalogClock> -> MinuteHand shadow
# <AnalogClock> -> HourHand shadow
# <AnalogClock> -> Main hands
# We can combine the two shadow hands into a single AnalogClock to reduce memory overhead and tick evaluations.
# We will do this via regex.

text = re.sub(
    r'<!-- Shadow minute hand - 12px offset down-right -->\s*<AnalogClock x="0" y="0" width="450" height="450">\s*(<MinuteHand[^>]+>\s*<Variant mode="AMBIENT" target="alpha" value="0"/>\s*</MinuteHand>)\s*</AnalogClock>\s*<!-- Shadow hour hand - 12px offset down-right -->\s*<AnalogClock x="0" y="0" width="450" height="450">\s*(<HourHand[^>]+>\s*<Variant mode="AMBIENT" target="alpha" value="0"/>\s*</HourHand>)\s*</AnalogClock>',
    r'''<!-- Shadow hands - 12px offset down-right -->
        <AnalogClock x="0" y="0" width="450" height="450">
          \2
          \1
        </AnalogClock>''',
    text
)

# Also disable Sweep ticks in AOD by ensuring the entire AnalogClock for the SecondHand is hidden.
# WFF engine skips Sweep frequency evaluations if the parent is hidden.
# We will add <Variant mode="AMBIENT" target="alpha" value="0"/> to the <AnalogClock> for second hands.
text = re.sub(
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">',
    r'<AnalogClock x="0" y="0" width="450" height="450" secondsPerCycle="60">\n              <Variant mode="AMBIENT" target="alpha" value="0"/>',
    text
)


# 2. GRANULAR COLORS FOR STEPS

# Let's replace the Expressions block
text = re.sub(
    r'<Expression name="missingSteps">\[STEP_GOAL\] == 0</Expression>\s*<Expression name="stepsHigh">\(\[STEP_COUNT\] \* 100 / \[STEP_GOAL\]\) >= 75</Expression>\s*<Expression name="stepsMedHigh">\(\[STEP_COUNT\] \* 100 / \[STEP_GOAL\]\) >= 50</Expression>\s*<Expression name="stepsMed">\(\[STEP_COUNT\] \* 100 / \[STEP_GOAL\]\) >= 25</Expression>',
    r'''<Expression name="missingSteps">[STEP_GOAL] == 0</Expression>
              <Expression name="stepsTier5">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 100</Expression>
              <Expression name="stepsTier4">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 80</Expression>
              <Expression name="stepsTier3">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 60</Expression>
              <Expression name="stepsTier2">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 40</Expression>
              <Expression name="stepsTier1">([STEP_COUNT] * 100 / [STEP_GOAL]) >= 20</Expression>''',
    text
)

# Regex to find and replace the Arc compares
def replace_arc_compares(match):
    # match.group(1) is the <Compare expression="missingSteps">...</Compare> block
    missing_block = match.group(1)
    
    # We need to extract the base arc template from the stepsHigh block
    high_block = match.group(2)
    # The high block looks like:
    # <Compare expression="stepsHigh">
    #   <PartDraw x="0" y="0" width="450" height="450">
    #     <Arc centerX="225" centerY="225" width="430" height="430" startAngle="270" endAngle="270" direction="CLOCKWISE">
    #       <Stroke color="#FF4CAF50" thickness="10" cap="ROUND"/>
    #       <Transform target="endAngle" value="270 + clamp([STEP_COUNT] / [STEP_GOAL], 0, 1) * 90"/>
    #     </Arc>
    #   </PartDraw>
    # </Compare>
    
    # We extract the inner content and replace the color
    inner_arc = re.search(r'<PartDraw[\s\S]*?</PartDraw>', high_block).group(0)
    
    def make_compare(tier, color):
        new_arc = re.sub(r'<Stroke color="[^"]+"', f'<Stroke color="{color}"', inner_arc)
        return f'<Compare expression="{tier}">{new_arc}</Compare>'

    new_compares = f'''{missing_block}
            {make_compare('stepsTier5', '#FF00E5FF')}
            {make_compare('stepsTier4', '#FF4CAF50')}
            {make_compare('stepsTier3', '#FF8BC34A')}
            {make_compare('stepsTier2', '#FFFFEB3B')}
            {make_compare('stepsTier1', '#FFFF9800')}
            <Default>{re.sub(r'<Stroke color="[^"]+"', '<Stroke color="#FFFF5252"', inner_arc)}</Default>'''
            
    return new_compares

# The pattern needs to match the missing block, and then all the old stepHigh, stepMedHigh, etc, until the closing </Condition>
# BUT there are also the text blocks. We must differentiate Arc compares from Text compares.
# Text compares have <PartText

text = re.sub(
    r'(<Compare expression="missingSteps">\s*<PartDraw[\s\S]*?</Compare>)\s*(<Compare expression="stepsHigh">[\s\S]*?</Compare>)\s*<Compare expression="stepsMedHigh">[\s\S]*?</Compare>\s*<Compare expression="stepsMed">[\s\S]*?</Compare>\s*<Default>[\s\S]*?</Default>',
    replace_arc_compares,
    text
)


# Now Regex to find and replace the Text compares
def replace_text_compares(match):
    missing_block = match.group(1)
    high_block = match.group(2)
    
    inner_text = re.search(r'<PartText[\s\S]*?</PartText>', high_block).group(0)
    
    def make_compare(tier, color):
        new_text = re.sub(r'color="[^"]+"', f'color="{color}"', inner_text)
        return f'<Compare expression="{tier}">{new_text}</Compare>'

    new_compares = f'''{missing_block}
                {make_compare('stepsTier5', '#FF00E5FF')}
                {make_compare('stepsTier4', '#FF4CAF50')}
                {make_compare('stepsTier3', '#FF8BC34A')}
                {make_compare('stepsTier2', '#FFFFEB3B')}
                {make_compare('stepsTier1', '#FFFF9800')}
                <Default>{re.sub(r'color="[^"]+"', 'color="#FFFF5252"', inner_text)}</Default>'''
                
    return new_compares

text = re.sub(
    r'(<Compare expression="missingSteps">\s*<PartText[\s\S]*?</Compare>)\s*(<Compare expression="stepsHigh">[\s\S]*?</Compare>)\s*<Compare expression="stepsMedHigh">[\s\S]*?</Compare>\s*<Compare expression="stepsMed">[\s\S]*?</Compare>\s*<Default>[\s\S]*?</Default>',
    replace_text_compares,
    text
)

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(text)

