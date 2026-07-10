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


def get_static_url():
    """Build a safe https:// base URL for files in the /static folder.

    NOTE: request.url_root already ends with a trailing slash (e.g. 'https://xxx.vercel.app/'),
    so we just append 'static' (no leading slash) to avoid a double slash.
    We also only replace 'http://' -> 'https://' (with '://'), so we never
    accidentally mangle an already-https URL into 'httpss://'.
    """
    return request.url_root.replace("http://", "https://", 1) + 'static'


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


# 訊息事件 (merged into a single handler)
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
                        LocationMessage(
                            title='Location',
                            address="YiLan",
                            latitude=24.781609811337216,
                            longitude=121.76645135904401
                        )
                    ]
                )
            )

        elif text == '詳情':
            url = get_static_url()

            image_carousel_template = ImageCarouselTemplate(
                columns=[
                    # 關於我們-選項
                    ImageCarouselColumn(
                        image_url=url + '/about-us.png',
                        action=PostbackAction(
                            label='品牌介紹',
                            data='action=about-us'
                        )
                    ),
                    # 房型介紹-選項
                    ImageCarouselColumn(
                        image_url=url + '/room-type.png',
                        action=PostbackAction(
                            label='房型介紹',
                            data='action=room'
                        )
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/check-in-guide.png',
                        action=PostbackAction(
                            label='入住須知',
                            data='action=service'
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


# Postback
@line_handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        url = get_static_url()

        # 第一層：點擊「我們的服務」 -> 彈出第二層圖片選單
        if data == 'action=service':
            sub_service_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/service_a.png',
                        action=PostbackAction(
                            label='服務A',
                            data='action=service_a'
                        )
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/service_b.png',
                        action=PostbackAction(
                            label='服務B',
                            data='action=service_b'
                        )
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/service_c.png',
                        action=PostbackAction(
                            label='服務C',
                            data='action=service_c'
                        )
                    ),
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TemplateMessage(
                            alt_text='服務選項',
                            template=sub_service_template
                        )
                    ]
                )
            )

        # 關於我們-圖片詳細
        elif data == 'action=about-us':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-about-us.png',
                            preview_image_url=url + '/detail-about-us.png'
                        )
                    ]
                )
            )
        
        # 房間類型-圖片詳情
        elif data == 'action=room':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/room-details.jpg',
                            preview_image_url=url + '/room-details.jpg'
                        )
                    ]
                )
            )

        # 服務子選單中點擊的結果
        elif data == 'action=service_a':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="這是服務A的詳細介紹")]
                )
            )

        elif data == 'action=service_b':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="這是服務B的詳細介紹")]
                )
            )

        elif data == 'action=service_c':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="這是服務C的詳細介紹")]
                )
            )


if __name__ == "__main__":
    app.run()
