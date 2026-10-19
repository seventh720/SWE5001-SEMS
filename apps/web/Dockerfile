FROM nginx:stable-alpine
RUN apk upgrade --no-cache
COPY dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
