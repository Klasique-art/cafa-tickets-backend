from rest_framework import serializers

class BotAssistantPromptSerializer(serializers.Serializer):
    prompt = serializers.CharField(
        help_text="The prompt text to be sent to the bot assistant.",
        max_length=2000,
    )
    context = serializers.JSONField(
        help_text="Additional context information for the bot assistant.",
        required=False,
    )
