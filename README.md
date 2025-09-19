# !При тестировании напишите нам, чтобы мы включили GPU-сервер для обеспечения вычислительных мощностей. Спасибо за понимание!

1.  Заходим на https://m2-live.store/
2.  Вводим данные от пользователя (Модертора), логин и пароль на яндекс диске. 
3.  Нажимаем на кнопку «Создать вакансию» и прикрепляем файл с описанием вакансии.
4.  Нажимаем на кнопку «Добавить кандидата», выбираем к какой вакансии добавлять кандидатов, прикрепляем файлы резюме и ожидаем пока наши алгоритмы обработают резюме (окно добавления файлов пропадет после завершения обработки).
5.  Для подключения к собеседованию можно нажать на кнопку «собеседование» у кандидата (на главной странице, либо на странице кандидата), скопируется ссылка на конференцию  или нажать на кандидата, что откроет подробную информацию о нем и нажать на кнопку «подключиться» в блоке «Управление собеседованием», после переадресации, введите свое имя (которое будет отображаться в комнате).
6.  После входа в комнату конференции (разрешите доступ к микрофону) к вам присоединится наш HR-Агент, который начнет проводить собеседование. У вас будет возможность отключить/включить микрофон, настроить устройство ввода/вывода аудио, громкость собеседника.
7.  После того, как HR-Агент сообщил о завершении собеседования, вы можете отключиться от комнаты и ожидать отчет о пройденном собеседовании (на странице кадидата) внизу в окне с подробной информации о кандидате (от лица которого подключились).

Подробнее всё показанно в нашем видео



# M2 Moderation Stack (HR + Video)

Набор сервисов для модерации HR-контента и видеовстреч:

* **Модераторская панель (Frontend/Vue)** — интерфейс модератора для вакансий/кандидатов.
  Repo: [https://github.com/M2-SYNDICATE/vue-moderator-s-panel-hr](https://github.com/M2-SYNDICATE/vue-moderator-s-panel-hr)
* **Бэкенд FastAPI** — REST/AI-логика для панели.
  Repo: [https://github.com/M2-SYNDICATE/back-m2-moder-panel](https://github.com/M2-SYNDICATE/back-m2-moder-panel)
* **Сервис видеоконференций (LiveKit + Vue)** — клиент для комнат и токен-сервер.
  Repo: [https://github.com/M2-SYNDICATE/livekit-vue-m2talk](https://github.com/M2-SYNDICATE/livekit-vue-m2talk)
* **HR-агент (Python)** — голос/валидация ответов и интеграция с LiveKit.
  Repo: [https://github.com/M2-SYNDICATE/hr-agent](https://github.com/M2-SYNDICATE/hr-agent)

> Цель файла — дать **короткие базовые шаги** для локального развёртывания. Подробности и любые отличия — см. README/код соответствующих репозиториев.

---

## Архитектура

```
[Vue HR Moderator Panel]  --(HTTP/JSON)-->  [FastAPI Backend]
        |                                          |
        | (вызовы/линки)                           | (интеграции/AI)
        v                                          v
[LiveKit Vue Client + Token Server] <--> [LiveKit Cloud/Server]
        ^
        | (WebRTC/события)
[HR Agent (Python): STT/TTS, логика]
```

---

## Требования

* Node.js LTS + npm
* Python 3.10+ (рекомендуется venv)
* Данные доступа к LiveKit (если используете видеокомнаты): `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

---

## Шаги запуска

### 1) Бэкенд (FastAPI)

Repo: [https://github.com/M2-SYNDICATE/back-m2-moder-panel](https://github.com/M2-SYNDICATE/back-m2-moder-panel)

```bash
# Клонируем и заходим
git clone https://github.com/M2-SYNDICATE/back-m2-moder-panel.git
cd back-m2-moder-panel

# (Опционально) создаём и активируем venv
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Ставим зависимости (если есть requirements.txt/pyproject)
pip install -r requirements.txt

# Запуск dev-сервера FastAPI
python main.py 
```

**Окружение:**

```

OPENROUTER_API_KEY=<ваш токен>
MY_CUSTOM_SERVICE_TOKEN=4mfnqusmo3hwmzv8rc0ngi1ej2bhnt #не менять иначе агент не сможет делать запросы

```

---

### 2) Видеосервис (LiveKit + Vue + token-server)

Repo: [https://github.com/M2-SYNDICATE/livekit-vue-m2talk](https://github.com/M2-SYNDICATE/livekit-vue-m2talk)

```bash
# Клонируем и заходим
git clone https://github.com/M2-SYNDICATE/livekit-vue-m2talk.git
cd livekit-vue-m2talk


npm install
# Запуск dev (по умолчанию Vite ~5173)
npm run build
```




**Token-server (в папке `token-server`):**

```bash
cd token-server
npm install
node server.js   # или npm start, если определено в package.json
```


---

### 3) Модераторская панель (Vue)

Repo: [https://github.com/M2-SYNDICATE/vue-moderator-s-panel-hr](https://github.com/M2-SYNDICATE/vue-moderator-s-panel-hr)

```bash
git clone https://github.com/M2-SYNDICATE/vue-moderator-s-panel-hr.git
cd vue-moderator-s-panel-hr


npm install
npm run build
```
**Окружение:**


```

VITE_API_BASE_URL=https://<ваш домен для сорвиса собеседований>/crud/crud

```
---

### 4) Настройка nginx

```nginx
#user http;
worker_processes  1;

#error_log  logs/error.log;
#error_log  logs/error.log  notice;
#error_log  logs/error.log  info;

#pid        logs/nginx.pid;


# Load all installed modules
include modules.d/*.conf;

events {
    worker_connections  1024;
}


http {
    include       mime.types;
    default_type  application/octet-stream;

    #log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
    #                  '$status $body_bytes_sent "$http_referer" '
    #                  '"$http_user_agent" "$http_x_forwarded_for"';

    #access_log  logs/access.log  main;

    sendfile        on;
    #tcp_nopush     on;

    #keepalive_timeout  0;
    keepalive_timeout  65;


	server {
    server_name  <Ваш домен для сервиса проведения собеседований>;
    
    # Проксирование для LiveKit WebSocket и HTTP API
    location /rtc {
        proxy_pass http://127.0.0.1:7880; # Указываем внутренний порт LiveKit
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Требуется для WebSocket
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400; # Увеличьте таймаут для долгоживущих соединений

        # Отключаем буферизацию для WebRTC
        proxy_buffering off;
    }
    
    
    
    location / {
	   root   <путь до проекта сервиса для собесдований>/dist/;
	   index  index.html index.htm;

	   try_files $uri $uri/ /index.html;
    }

    
    location /api/ {
        proxy_pass http://127.0.0.1:3001/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    listen 443 ssl; # managed by Certbot
    
    ssl_certificate <ssl сертификат>; # managed by Certbot
    ssl_certificate_key <ssl ключ>; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot

   

}
    server {
    if ($host = <Ваш домен для сервиса проведения собеседований>) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen       80;
    server_name  <Ваш домен для сервиса проведения собеседований>;
    return 404; # managed by Certbot


}
	# Для панели модераторов
	server {
		server_name <Ваш домен для панели модератора>;
		location / {
			root <путь до проекта панели модератора>/dist;
			index index.html index.htm;
			try_files $uri /index.html; 
			
		}
		location /crud/ {
	       proxy_pass http://localhost:2856/;
	       proxy_http_version 1.1;
	       proxy_set_header Host $host;
	       proxy_set_header X-Real-IP $remote_addr;
	       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
	       proxy_set_header X-Forwarded-Proto $scheme;
		 }
	
    listen 443 ssl; # managed by Certbot
    ssl_certificate <ssl сертификат>; # managed by Certbot
    ssl_certificate_key <ssl ключ>; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot

}




	server {
    if ($host = <Ваш домен для панели модератора>) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


		server_name <Ваш домен для панели модератора>;
		listen 80;
    return 404; # managed by Certbot


}}

```
---

### 5) Установка LiveKit

```bash
mkdir livekit
cd livekit
curl -sSL https://get.livekit.io | bash
micro livekit.yaml
livekit-server --config ~/livekit/livekit.yaml
```
**Содержимое livekit.yaml:**
```
# Основные настройки API
port: 7880

keys:
  devkey: secretsecretsecretsecretsecretsecret

# Адреса для бинда
bind_addresses:
  - 127.0.0.1


rtc:
  node_ip: <ip сервера>
  port_range_start: 50000
  port_range_end: 50050
  use_external_ip: true

# Настройки комнат
room:
  empty_timeout: 300

# Настройки TURN/STUN
turn:
  enabled: true
  udp_port: 3478
```

---

### 6) HR-агент (Python)

Repo: [https://github.com/M2-SYNDICATE/hr-agent](https://github.com/M2-SYNDICATE/hr-agent)

```bash
git clone https://github.com/M2-SYNDICATE/hr-agent.git
cd hr-agent

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt || true

# Возможные точки входа (по названиям файлов в репо):


python stt_server_v2.py

python tts_client.py

python livekit_agent.py
```

**Окружение:**
```
LIVEKIT_URL=http://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secretsecretsecretsecretsecretsecret
OPENROUTER_API_KEY=<ваш ключ>
```
---

## Порядок запуска

1. **Бэкенд**
2. **Token-server**
3. **LiveKit Vue клиент**
4. **Модераторская панель**
5. **HR-агент** 

---


## Быстрые проверки

* Бэкенд отвечает на `GET http://localhost:2856/`
* Панель открывается в браузере.
* Видеоклиент подключается к комнате LiveKit; токены выдаёт `token-server`.
* HR-агент подключается к LiveKit (проверьте логи и переменные окружения).

---

## Полезные ссылки

* Панель (Vue): [https://github.com/M2-SYNDICATE/vue-moderator-s-panel-hr](https://github.com/M2-SYNDICATE/vue-moderator-s-panel-hr)
* Бэкенд (FastAPI): [https://github.com/M2-SYNDICATE/back-m2-moder-panel](https://github.com/M2-SYNDICATE/back-m2-moder-panel)
* Видеосервис (LiveKit + Vue): [https://github.com/M2-SYNDICATE/livekit-vue-m2talk](https://github.com/M2-SYNDICATE/livekit-vue-m2talk)
* HR-агент (Python): [https://github.com/M2-SYNDICATE/hr-agent](https://github.com/M2-SYNDICATE/hr-agent)