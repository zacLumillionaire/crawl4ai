# 使用 Python 基礎映像檔
FROM python:3.11-slim

# 安裝 Playwright 瀏覽器所需的套件
RUN apt-get update && apt-get install -y \
    wget gnupg curl ca-certificates fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdbus-1-3 libdrm2 libgtk-3-0 libnspr4 libnss3 \
    libxcomposite1 libxdamage1 libxrandr2 xdg-utils \
    libgbm1 libxshmfence1 libxss1 libappindicator3-1 \
    && apt-get clean

# 建立工作目錄
WORKDIR /app

# 複製專案檔案
COPY . /app

# 安裝 Python 套件
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 安裝 Playwright 瀏覽器
RUN playwright install --with-deps

# 啟動應用程式
CMD ["python", "4ai.py"]