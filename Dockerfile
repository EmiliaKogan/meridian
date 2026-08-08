# start from an existing image (the base layer)
FROM python:3.14

# set the working directory for everything that follows
WORKDIR /app

# copy a file from your project into the image
COPY pyproject.toml uv.lock ./

# install a tool AT BUILD TIME (see "layers" below for why this comes first)
# Install uv inside the image
RUN pip install uv

# Install the locked project dependencies
RUN uv sync --frozen

# copy a file from your project into the image
# Copy the application source code
COPY src ./src

# Copy the Alembic configuration and migrations
COPY alembic ./alembic
COPY alembic.ini .

#set an environment variable baked into the image
# Make the application package available to Python
ENV PYTHONPATH=/app/src

# # the command that runs when a container STARTS from this image
# CMD ["uv", "run", "python", "-m", "trip_ingest", "/data/drops"]