# Floors Complication ProGuard Rules

# Keep complication service
-keep class com.photoface.floors.FloorsComplicationService { *; }

# Health Services
-keep class androidx.health.services.client.** { *; }
