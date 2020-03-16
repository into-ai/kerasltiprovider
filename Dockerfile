FROM tensorflow/tensorflow:latest-py3

ENV PORT: 3000
ARG TEMPLATE_DIR=/templates/
ENV TEMPLATE_DIR="${TEMPLATE_DIR}"

WORKDIR /app
COPY . /app
COPY kerasltiprovider/templates/* $TEMPLATE_DIR/

RUN ls -lia ${TEMPLATE_DIR}
RUN pip install --upgrade pip pipenv
RUN pipenv install --system --deploy --clear

ENTRYPOINT [ "python", "serve.py" ]