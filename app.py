import csv
import smtplib
from datetime import date, datetime
from datetime import timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pdfkit
import pyrebase
from firebase import firebase
from flask import Flask, request, make_response, jsonify
from jinja2 import Environment, FileSystemLoader
from twilio.rest import Client

import config

app = Flask(__name__)

config = {
    "apiKey": config.apikey,
    "authDomain": config.authDomain,
    "databaseURL": config.databaseURL,
    "storageBucket": config.storageBucket,
    "serviceAccount": config.firebasesdk,
    "twilioSID": config.twilioSID,
    "twilioAUTH": config.twilioAUTH,
    "appPWD": config.appPWD,
    "fromEmail": config.fromEmail
}

firebaseObj = pyrebase.initialize_app(config)
fb_app = firebase.FirebaseApplication(config['databaseURL'], None)


@app.route('/')
def index():
    return 'Hello World!'


def getAction():
    req = request.get_json(force=True)
    action = req.get('queryResult').get('action')
    return action


def getUser():
    phone = getPhone()
    return fb_app.get('/users', phone)


def getPhone():
    req = request.get_json(force=True)
    return req.get('session')[-13:]


def getParams(key=None):
    req = request.get_json(force=True)
    if key is None:
        return req.get('queryResult').get('parameters')
    else:
        return req.get('queryResult').get('parameters')[key]


def getUserOrder():
    sess = getSession()
    return fb_app.get('/orders', sess)


def getSession():
    return getPhone() + "-" + str(date.today())


def pushToDB():
    db = firebaseObj.database()
    params = getParams()
    sess = getSession()
    curr_orders = getUserOrder()
    if curr_orders is not None:
        item_list = params['items']
        num_list = params['number']
        order_dict = curr_orders
        poslist = []
        neglist = []
        for i in range(len(item_list)):
            price = get_price(item_list[i])
            if item_list[i] not in order_dict:
                if price != -1:
                    temp = {item_list[i]: [int(num_list[i]), price]}
                    order_dict.update(temp)
                    poslist.append(item_list[i])
                else:
                    neglist.append(item_list[i])
            else:
                prev = order_dict[item_list[i]][0]
                order_dict[item_list[i]][0] = prev + int(num_list[i])
                poslist.append(item_list[i])
        db.child('orders').child(sess).update(order_dict)
    else:
        item_list = params['items']
        num_list = params['number']
        order_dict = {}
        poslist = []
        neglist = []
        for i in range(len(item_list)):
            price = get_price(item_list[i])
            if price != -1:
                temp = {item_list[i]: [int(num_list[i]), price]}
                order_dict.update(temp)
                poslist.append(item_list[i])
            else:
                neglist.append(item_list[i])
        db.child('orders').child(sess).set(order_dict)
    text = ""
    if len(neglist) != 0:
        i = 0
        text = "Sorry, we don't sell "
        for item in neglist:
            if i == (len(neglist) - 2):
                text += item + " and "
            elif i == (len(neglist) - 1):
                text += item + ". "
            else:
                text += item + ", "
            i += 1
        text += "Please refer to the list we sent you earlier. "
        if len(poslist) != 0:
            text += "However, we have added "
            i = 0
            for item in poslist:
                if i == (len(poslist) - 2):
                    text += item + " and "
                elif i == (len(poslist) - 1):
                    text += item
                else:
                    text += item + ", "
                i += 1
            text += " to your cart."
    return text


def get_price(item):
    with open('items.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                line_count += 1
                continue
            else:
                if row[0] == item:
                    return int(row[1])
        return -1


def sendPDF(url):
    username = config['twilioSID']
    password = config['twilioAUTH']
    client = Client(username=username, password=password)
    from_whatsapp_number = 'whatsapp:+14155238886'
    to_whatsapp_number = getPhone()
    client.messages.create(body='EssentialsKart Products',
                           media_url=url,
                           from_=from_whatsapp_number,
                           to=to_whatsapp_number)
    ch_contact = getUser()
    if ch_contact is not None:
        name = ch_contact['name']
        client.messages.create(
            body='Hey ' + name + '! Glad to see you again. It\'s Natasha again from EssentialsKart. Here to help you '
                                 'out in your order. '
                                 'Please check the list below to find the essential items that you can order '
                                 'during lockdown. So, what would you like to order today?',
            from_=from_whatsapp_number,
            to=to_whatsapp_number)
    else:
        client.messages.create(
            body='Hey! I am Natasha from EssentialsKart. Here to help you out in your order. '
                 'Please check the list below to find the essential items that you can order '
                 'during lockdown. So, what would you like to order today?',
            from_=from_whatsapp_number,
            to=to_whatsapp_number)
    return ""


def genPDF(users, phone, pickup):
    sums = 0
    dates = datetime.now()
    todays_date = dates.strftime("%A,%d %B,%Y")
    delivery = dates + timedelta(days=7)
    delivery_date = delivery.strftime("%A,%d %B,%Y")
    orders = getUserOrder()
    db = firebaseObj.database()
    invoice = len(db.child('orders').get().val())
    for key in orders:
        sums += orders[key][0] * orders[key][1]
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template("templates/invoice.html")
    template_vars = {'users': users, 'orders': orders, "todays_date": todays_date, "delivery_date": delivery_date,
                     "sum": sums, 'phone': phone, 'invoice': invoice, 'pickup': pickup}
    html_out = template.render(template_vars)
    path_to_wkhtml2pdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    config1 = pdfkit.configuration(wkhtmltopdf=path_to_wkhtml2pdf)
    pdf = pdfkit.from_string(html_out, False, configuration=config1)
    return pdf


def del_sess():
    sess = getSession()
    fb_app.delete('/orders', sess)
    return ""


def check_phone():
    ch_contact = getUser()
    if ch_contact is not None:
        name = ch_contact['name']
        return name + ", please enter your passcode to proceed."
    else:
        return "We have to setup an account for you to proceed further. Please enter your name."


def conf_details():
    details = getParams()
    contact = getPhone()
    db = firebaseObj.database()
    details_dict = {'name': details['name']['name'].title(), 'email': details['email'], 'zipcode': details['zipcode']}
    db.child('users').child(contact).set(details_dict)
    return ""


def get_order():
    curr_orders = getUserOrder()
    text = ""
    i = 1
    sums = 0
    for item in curr_orders:
        sums += curr_orders[item][0] * curr_orders[item][1]
        text += "{}. {}     {}  x    Rs. {}  =>  Rs. {}<br>".format(i, item.title(), curr_orders[item][0],
                                                                    curr_orders[item][1],
                                                                    (curr_orders[item][0] * curr_orders[item][1]))
        i += 1
    text += "Grand Total: {}<br>".format(sums)
    return text


def check_pwd():
    password = getUser()['passcode']
    passcode = getParams('passcode')
    if password != passcode:
        return "Wrong passcode. Please try again."
    else:
        return "Authentication successful. Would you like to pay cash on delivery or by card?"


def add_pwd():
    phone = getPhone()
    passcode = getParams('new_passcode')
    ph = getUser()
    if len(str(int(passcode))) == 4 and str(int(passcode)).isnumeric():
        ph.update({'passcode': passcode})
        db = firebaseObj.database()
        db.child('users').child(phone).update(ph)
        return "Congrats, " + ph['name'] + "! You are all set. Would you like to pay cash on delivery or by card?"
    else:
        return "Please enter a valid 4 digit numerical passcode."


def add_mode():
    phone = getPhone()
    mode = getParams('mop')
    ph = getUser()
    ph['mode'] = mode
    db = firebaseObj.database()
    db.child('users').child(phone).update(ph)
    order = get_order()
    return "Okay. This is your order summary.<br>" + order + " Reply 'Yes' to confirm order and 'No' to modify."


def conf_order():
    users = getUser()
    zipcode = users['zipcode']
    pickup_list = get_pincode_list(zipcode)
    text = "Please type the number of the nearest pickup point from the list below-<br>"
    i = 0
    for point in pickup_list:
        i += 1
        text += "{}. {}<br>".format(i, point)
    return text


def sendmail(to_email, message, pdf):
    from_email = config['fromEmail']
    password = config['appPWD']
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Your EssentialsKart order has been confirmed."
    msg['From'] = from_email
    msg['To'] = to_email
    msgText = MIMEText(message, 'html')
    msg.attach(msgText)
    msgpdf = MIMEApplication(pdf, _subtype="pdf")
    msgpdf.add_header('Content-Disposition', 'attachment', filename='invoice')
    msg.attach(msgpdf)
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(from_email, password)
            s.sendmail(from_email, to_email, msg.as_string())
        response = "Success"
    except Exception as err:
        print(err)
        response = "Failed"
    return response


def edit_order():
    db = firebaseObj.database()
    sess = getSession()
    orders = getUserOrder()
    params = getParams()
    item_list = params['items']
    num_list = params['number']
    order_dict = dict(orders)
    neglist = []
    for i in range(len(item_list)):
        price = get_price(item_list[i])
        if item_list[i] not in order_dict:
            if int(num_list[i]) != 0:
                if price != -1:
                    temp = {item_list[i]: [int(num_list[i]), price]}
                    order_dict.update(temp)
                else:
                    neglist.append(item_list[i])
        else:
            if int(num_list[i]) == 0:
                del order_dict[item_list[i]]
            else:
                order_dict[item_list[i]][0] = int(num_list[i])
    db.child('orders').child(sess).set(order_dict)
    text = ""
    if len(neglist) != 0:
        text = "Some things were not added due to unavailability."
    return "Okay, the requested changes have been made.<br>{}<br>{}<brReply 'Yes' to confirm else keep typing in the " \
           "same format for any further changes.".format(get_order(), text)


def edit_details():
    phone = getPhone()
    params = getParams()
    data = getUser()
    for key in params:
        if params[key] != "":
            if key == "name1":
                data[key.replace("1", "")] = params['name1']['name']
            else:
                data[key.replace("1", "")] = params[key]
    db = firebaseObj.database()
    db.child('users').child(phone).set(data)
    return "Are your details correct now?<br>Name: {}<br>Email: {}<br>Zip code: {}".format(data['name'], data['email'],
                                                                                           data['zipcode'])


def get_pincode_list(zipcode):
    pickup_list = []
    with open('zipcodes.csv', 'r') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            if row[1] == zipcode:
                if row[3] == 'NA' or row[3] == row[4]:
                    point = "{}, {}, {} - {}".format(row[0].strip(), row[2].strip(), row[4].strip(), row[1].strip())
                else:
                    point = "{}, {}, {}, {} - {}".format(row[0].strip(), row[2].strip(), row[3].strip(), row[4].strip(),
                                                         row[1].strip())
                pickup_list.append(point)
            elif len(pickup_list) > 0:
                break
    return pickup_list


def add_pickup():
    phone = getPhone()
    users = getUser()
    pickupNo = int(getParams('number'))
    zipcode = users['zipcode']
    pickup_list = get_pincode_list(zipcode)
    if pickupNo <= len(pickup_list):
        pickup = pickup_list[pickupNo - 1]
    else:
        pickup = pickup_list[0]
    pdf = genPDF(users, phone, pickup)  # here we'll receive a pdf
    email = users['email']
    name = users['name']
    message = "Hey {},<br> Thank you for ordering with us. We hope you find our services useful. Here is your invoice." \
        .format(name)
    text = sendmail(email, message, pdf)
    if text == "Success":
        return "Thank you for your order. We have sent the invoice to your registered email."
    else:
        return "There was some problem in sending your invoice."


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    action = getAction()
    text = ''
    if action == 'order_items':  # save items to session
        text = pushToDB()
    elif action == 'input.welcome':  # send the items pdf
        url = "https://github.com/ItsTheKayBee/chatbot-webhook-API/raw/master/price_list.pdf"
        text = sendPDF(url)
    elif action == 'OrderItems.OrderItems-cancel':  # delete the session and end it
        text = del_sess()
    elif action == 'confirm_details':  # ask for confirmation about order
        text = conf_details()
    elif action == 'confirm_order':  # send final receipt over email and wapp
        text = conf_order()
    elif action == 'edit_order':  # edit order
        text = edit_order()
    elif action == 'edit_details':  # edit individual detail
        text = edit_details()
    elif action == 'stop_order':  # check phone
        text = check_phone()
    elif action == 'check_passcode':  # check passcode
        text = check_pwd()
    elif action == 'get_passcode':  # store passcode
        text = add_pwd()
    elif action == 'mode':  # store mode
        text = add_mode()
    elif action == 'get_pickup':  # store mode
        text = add_pickup()
    reply = {
        "fulfillmentText": text,
    }
    return make_response(jsonify(reply))


if __name__ == '__main__':
    app.run()
