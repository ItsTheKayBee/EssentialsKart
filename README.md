# EssentialsKart Webhook
EssentialsKart chatbot helps a user in ordering items from a store or a supermarket. This is a webhook for the same, made in Python flask. This endpoint has to be connected to the chatbot platform like in my case, dialogflow. You can choose the platform of your choice. And then, the application can be deployed on any platform- WhatsApp, Facebook Messenger, Slack, Telegram, etc. In may case it is WhatsApp, using Twilio.

## Features
1. Read orders.  
2. Store on firebase.
3. Calculate the nearest location according to the user.
4. Send an auto-generated invoice to the user's email.

## Installation-
```bash
git clone https://github.com/ItsTheKayBee/EssentialsKart.git
cd EssentialsKart
pip install flask, pdfkit, twilio, pyrebase, python-firebase
flask run
```
