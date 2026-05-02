import re

with open('complications/src/main/java/com/photoface/complications/sunrise/SunriseComplicationService.kt', 'r') as f:
    text = f.read()

# Add imports for PendingIntent and Intent if not present
if 'import android.app.PendingIntent' not in text:
    text = re.sub(
        r'import android.content.ComponentName',
        'import android.content.ComponentName\nimport android.content.Intent\nimport android.app.PendingIntent\nimport com.photoface.complications.floors.PermissionActivity',
        text
    )

# Helper function to create tap action
tap_action_code = """
    private fun getPermissionTapAction(): PendingIntent {
        val intent = Intent(this, PermissionActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun createNoLocationShortText()"""

text = text.replace('    private fun createNoLocationShortText()', tap_action_code)

# Add setTapAction to NoLocation builders
text = text.replace(
    '.setMonochromaticImage(',
    '.setTapAction(getPermissionTapAction())\n            .setMonochromaticImage(',
    2 # Only replace the two NoLocation ones, actually wait, replace all of them if they are in the NoLocation methods. Let's do it smarter.
)
with open('complications/src/main/java/com/photoface/complications/sunrise/SunriseComplicationService.kt', 'w') as f:
    f.write(text)
