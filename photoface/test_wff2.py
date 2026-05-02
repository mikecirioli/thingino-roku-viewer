import sys

with open('watchface/src/main/res/raw/watchface.xml', 'r') as f:
    text = f.read()

test_xml = """<ListConfiguration id="quadrant1Widget">
        <Condition>
          <Expressions>
            <Expression name="hasHR">[HAS_HEART_RATE_SENSOR]</Expression>
          </Expressions>
          <Compare expression="hasHR">
            <ListOption id="2">
              <Group x="0" y="0" width="10" height="10"/>
            </ListOption>
          </Compare>
          <Default>
            <ListOption id="2">
              <Group x="0" y="0" width="10" height="10"/>
            </ListOption>
          </Default>
        </Condition>
"""

new_text = text.replace('<ListConfiguration id="quadrant1Widget">', test_xml)

with open('watchface/src/main/res/raw/watchface.xml', 'w') as f:
    f.write(new_text)
