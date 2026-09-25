# The image is built from the monorepo root, as a real one also packs the web.
FROM python:3.12-slim

WORKDIR /app
COPY apps/api/src ./src
ENV PYTHONPATH=/app/src

USER 10001
CMD ["python", "-c", "import example_api; print(example_api.greet('image'))"]
