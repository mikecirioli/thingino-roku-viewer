import sys

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

test_xml = """<Scene backgroundColor="#FF000000">
    <Condition>
      <Expressions>
        <Expression name="testHasHR">[HAS_HEART_RATE_SENSOR]</Expression>
        <Expression name="testHasSteps">[HAS_STEP_COUNT_SENSOR]</Expression>
      </Expressions>
      <Compare expression="testHasHR"><PartDraw x="0" y="0" width="1" height="1"><Line startX="0" startY="0" endX="1" endY="1"><Stroke color="#FF0000" thickness="1"/></Line></PartDraw></Compare>
      <Default><PartDraw x="0" y="0" width="1" height="1"><Line startX="0" startY="0" endX="1" endY="1"><Stroke color="#FF0000" thickness="1"/></Line></PartDraw></Default>
    </Condition>
"""

new_text = text.replace('<Scene backgroundColor="#FF000000">', test_xml)

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(new_text)
