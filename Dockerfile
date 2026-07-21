# use a slim Python 3.11 image as the base
FROM python:3.11-slim

# set the working directory inside the container
WORKDIR /app

# copy requirements first — Docker caches this layer
# so if requirements don't change, pip install is skipped on rebuild
COPY requirements-prod.txt .

# install dependencies
RUN pip install --no-cache-dir -r requirements-prod.txt

# copy the rest of the project
COPY . .

# expose the port Dash runs on
EXPOSE 8050

# command to run when the container starts
CMD ["python", "dashboard/app.py"]

# Run the following in the terminal
# docker build -t aqi-dashboard . 