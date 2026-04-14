# Use Shelf.io's LibreOffice Lambda Base Image (Python 3.12)
FROM public.ecr.aws/shelf/lambda-libreoffice-base:26.2-python3.12-x86_64

# Copy Lambda handler
COPY handler.py ${LAMBDA_TASK_ROOT}/

# Set Lambda handler
CMD [ "handler.handler" ]
