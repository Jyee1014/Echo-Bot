from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
    TemplateMessage,
    ButtonsTemplate,
    PostbackAction,
    LocationMessage,
    ImageCarouselTemplate,
    ImageCarouselColumn,
    URIAction
)
from linebot.v3.webhooks import (
    MessageEvent,
    FollowEvent,
    PostbackEvent,
    TextMessageContent
)

import os

app = Flask(__name__)

configuration = Configuration(access_token=os.getenv('CHANNEL_ACCESS_TOKEN'))
line_handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

# 加入好友事件
@line_handler.add(FollowEvent)
def handle_follow(event):
    print(f'Got {event.type} event')

# 訊息事件
@line_handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        text = event.message.text

        if text == '文字':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="這是文字訊息")]
                )
            )
        elif text == '位置':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        LocationMessage(title='Location', address="YiLan", latitude=24.781609811337216, longitude=121.76645135904401)
                    ]
                )
            )

@line_handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if text == '詳情':
            url = request.url_root + '/static'
            url = url.replace("http", "https")
            
            image_carousel_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/logo.png',
                        action=PostbackAction( 
                            label='我們的服務',
                            data='action=service'
                        )
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/logo.png',
                        action=PostbackAction(
                            label='房間類型',
                            data='action=room'
                        )
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/logo.png',
                        action=PostbackAction(
                            label='測試測試',
                            data='action=test'
                        )
                    ),
                ]
            )

            image_carousel_message = TemplateMessage(
                alt_text='滾輪選項',
                template=image_carousel_template
            )

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[image_carousel_message]
                )
            )

# Handle postback events
@line_handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        url = request.url_root + '/static'
        url = url.replace("http", "https")
        
        if data == 'action=service':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/service.png',
                            preview_image_url=url + '/service.png'
                        )
                    ]
                )
            )
        elif data == 'action=room':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/room.png',
                            preview_image_url=url + '/room.png'
                        )
                    ]
                )
            )
        elif data == 'action=test':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/logo.png',
                            preview_image_url=url + '/logo.png'
                        )
                    ]
                )
            )

if __name__ == "__main__":
    app.run()