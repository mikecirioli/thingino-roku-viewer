import re

with open('complications/src/main/java/com/photoface/complications/floors/FloorsComplicationService.kt', 'r') as f:
    text = f.read()

# Add imports for PendingIntent and Intent
text = re.sub(
    r'import android.content.ComponentName',
    'import android.content.ComponentName\nimport android.content.Intent\nimport android.app.PendingIntent',
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

    private fun createNoDataShortText()"""

text = text.replace('    private fun createNoDataShortText()', tap_action_code)

# Add setTapAction to NoData builders
text = text.replace(
    '.setMonochromaticImage(',
    '.setTapAction(getPermissionTapAction())\n            .setMonochromaticImage('
)

with open('complications/src/main/java/com/photoface/complications/floors/FloorsComplicationService.kt', 'w') as f:
    f.write(text)
