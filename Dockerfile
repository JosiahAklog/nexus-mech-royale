FROM python:3.13-slim-bookworm
WORKDIR /bot
COPY bot.py mechfight.py map.bin mapinfo.json fastmap.so /bot/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN chmod 0444 /bot/bot.py /bot/mechfight.py /bot/map.bin /bot/mapinfo.json /bot/fastmap.so
USER 65534:65534
ENTRYPOINT ["python3", "-u", "/bot/bot.py"]
