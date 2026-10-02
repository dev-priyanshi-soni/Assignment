from rest_framework import serializers

class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=200, trim_whitespace=True)
    finish = serializers.CharField(max_length=200, trim_whitespace=True)

    def validate(self, attrs):
        if attrs["start"].strip().lower() == attrs["finish"].strip().lower():
            raise serializers.ValidationError("Start and finish locations must be different.")
        return attrs
