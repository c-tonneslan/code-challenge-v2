import csv
import io

from rest_framework.renderers import BaseRenderer, JSONRenderer


class CSVRenderer(BaseRenderer):
    media_type = "text/csv"
    format = "csv"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if not data:
            return ""
        # Use the first row's keys as the header order. With DRF this is
        # stable because the serializer preserves field declaration order.
        fieldnames = list(data[0].keys())
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        return buf.getvalue()


__all__ = ["CSVRenderer", "JSONRenderer"]
