FROM apify/actor-python:3.11

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy staged studio package if pushed via stage_and_push.sh, or build from repo root.
COPY . ./
ENV PYTHONPATH="/usr/src/app/src:/usr/src/app"
RUN if [ -f pyproject.toml ] && [ -d src ]; then pip install --no-cache-dir --no-deps .; fi

CMD ["python3", "-m", "main"]
