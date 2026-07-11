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
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
    TemplateMessage,
    ButtonsTemplate,
    PostbackAction,
    LocationMessage,
    ImageCarouselTemplate,
    ImageCarouselColumn,
    URIAction,
    RichMenuSize,   # Rich的都是導覽
    RichMenuRequest,
    RichMenuArea,
    RichMenuBounds,
    MessageAction
)
from linebot.v3.webhooks import (
    MessageEvent,
    FollowEvent,
    PostbackEvent,
    TextMessageContent
)

import os
import requests
import json

app = Flask(__name__)

# NOTE: never hardcode secrets in source. Always read from environment variables.
CHANNEL_ACCESS_TOKEN = os.getenv('CHANNEL_ACCESS_TOKEN')
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
line_handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))


def get_static_url():
    """Build a safe https:// base URL for files in the /static folder."""
    return request.url_root.replace("http://", "https://", 1) + 'static'


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


# -----------------------------------------------------------------------
# Rich menu setup — THIS IS A ONE-TIME ADMIN ACTION, not something that
# should run automatically when the app boots. Call it manually by hitting
# /admin/setup-rich-menu once (see route below), then leave it alone.
# -----------------------------------------------------------------------
def create_rich_menu():
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_blob_api = MessagingApiBlob(api_client)

        headers = {
            'Authorization': 'Bearer ' + CHANNEL_ACCESS_TOKEN,
            'Content-Type': 'application/json'
        }

        # Adjust these bounds to match your actual rich menu artwork's layout.
        # Size below assumes a 2500x1686 image with two wide buttons on top
        # (線上訂房 / 客房導覽) and three boxes along the bottom
        # (餐飲|環境介紹 / 入住須知 / 交通|周邊景點).
        body = {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "導覽",
            "chatBarText": "導覽",
            "areas": [
                {
                    "bounds": {"x": 33, "y": 67, "width": 600, "height": 200},
                    "action": {"type": "message", "text": "線上訂房"}
                },
                {
                    "bounds": {"x": 1808, "y": 63, "width": 600, "height": 200},
                    "action": {"type": "message", "text": "客房導覽"}
                },
                {
                    "bounds": {"x": 47, "y": 846, "width": 792, "height": 769},
                    "action": {"type": "message", "text": "餐飲|環境介紹"}
                },
                {
                    "bounds": {"x": 833, "y": 846, "width": 826, "height": 769},
                    "action": {"type": "message", "text": "入住須知"}
                },
                {
                    "bounds": {"x": 1660, "y": 846, "width": 870, "height": 769},
                    "action": {"type": "message", "text": "交通|周邊景點"}
                },
            ]
        }

        response = requests.post(
            'https://api.line.me/v2/bot/richmenu',
            headers=headers,
            data=json.dumps(body).encode('utf-8')
        )
        response = response.json()
        print(response)
        rich_menu_id = response["richMenuId"]

        with open('static/navigation_menu.png', 'rb') as image:
            line_bot_blob_api.set_rich_menu_image(
                rich_menu_id=rich_menu_id,
                body=bytearray(image.read()),
                _headers={'Content-Type': 'image/jpeg'}
            )

        line_bot_api.set_default_rich_menu(rich_menu_id)
        return rich_menu_id


@app.route("/admin/setup-rich-menu", methods=['POST'])
def setup_rich_menu():
    """
    Hit this once manually (e.g. with curl or Postman) to create and set
    the rich menu. Do NOT call create_rich_menu() automatically at import
    time — that would create a new rich menu on every cold start.
    """
    rich_menu_id = create_rich_menu()
    return {"rich_menu_id": rich_menu_id}


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
        url = get_static_url()

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

        # -------------------------------------------------------------
        # Rich menu actions
        # -------------------------------------------------------------

        # 線上訂房 缺链接就完成
        elif text == '線上訂房':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/booking-price.jpg',
                            preview_image_url=url + '/booking-price.jpg'
                        ),
                        TextMessage(text="歡迎預約入住！請透過以下連結完成線上訂房：#訂房鏈接")
                    ]
                )
            )

        # 客房導覽 待确认
        elif text == '客房導覽':
            room_tour_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/room-a.png',
                        action=PostbackAction(label='房型A', data='action=room_a')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/room-b.png',
                        action=PostbackAction(label='房型B', data='action=room_b')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/room-c.png',
                        action=PostbackAction(label='房型C', data='action=room_c')
                    ),
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TemplateMessage(alt_text='客房導覽', template=room_tour_template)]
                )
            )

        # 餐飲|環境介紹 
        elif text == '餐飲|環境介紹':
            dining_env_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/dining.png',
                        action=PostbackAction(label='餐飲', data='action=dining')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/environment-bigpic.png',
                        action=PostbackAction(label='環境介紹', data='action=environment')
                    ),
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TemplateMessage(alt_text='餐飲環境介紹', template=dining_env_template)]
                )
            )

        # 入住須知 完成
        elif text == '入住須知':
            checkin_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/facility.png',
                        action=PostbackAction(label='設施', data='action=facility')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/detail-check-in-guide.png',
                        action=PostbackAction(label='入住須知', data='action=detail-checkin')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/pets.png',
                        action=PostbackAction(label='寵物入住須知', data='action=detail-pets')
                    ),
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TemplateMessage(alt_text='入住須知', template=checkin_template)]
                )
            )

        # 交通|周邊景點 待确认
        elif text == '交通|周邊景點':
            transport_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/transfer.png',
                        action=PostbackAction(label='接送', data='action=transfer')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/turtle-island.png',
                        action=PostbackAction(label='龜山島', data='action=turtle_island')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/old-street.png',
                        action=PostbackAction(label='老街', data='action=old_street')
                    ),
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TemplateMessage(alt_text='交通周邊景點', template=transport_template)]
                )
            )


# Postback
@line_handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        url = get_static_url()

        # ---- 客房導覽 子選項 ----
        if data == 'action=room_a':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/room-a-detail.png',
                            preview_image_url=url + '/room-a-detail.png'
                        )
                    ]
                )
            )
        elif data == 'action=room_b':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/room-b-detail.png',
                            preview_image_url=url + '/room-b-detail.png'
                        )
                    ]
                )
            )
        elif data == 'action=room_c':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/room-c-detail.png',
                            preview_image_url=url + '/room-c-detail.png'
                        )
                    ]
                )
            )

        # ---- 餐飲|環境介紹 子選項 ----
        elif data == 'action=dining':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/dining-detail.png',
                            preview_image_url=url + '/dining-detail.png'
                        )
                    ]
                )
            )
        elif data == 'action=environment':
            environment_carousel_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/environment-pic1.png',
                        action=PostbackAction(label='悠然自得', data='action=noop', display_text=' ')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/environment-pic2.png',
                        action=PostbackAction(label='館內泳池', data='action=noop', display_text=' ')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/environment-pic3.png',
                        action=PostbackAction(label='停車場地', data='action=noop', display_text=' ')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/environment-pic4.png',
                        action=PostbackAction(label='一樓大廳', data='action=noop', display_text=' ')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/environment-pic5.png',
                        action=PostbackAction(label='二樓交誼庭', data='action=noop', display_text=' ')
                    ),
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TemplateMessage(alt_text='環境介紹', template=environment_carousel_template)]
                )
            )

        # ---- 入住須知 子選項 ---- 完成
        elif data == 'action=facility':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-facility.png',
                            preview_image_url=url + '//detail-facility.png'
                        )
                    ]
                )
            )
        
        elif data == 'action=detail-checkin':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-checkin.png',
                            preview_image_url=url + '/detail-checkin.png'
                        )
                    ]
                )
            )
        
        elif data == 'action=detail-pets':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-pets.png',
                            preview_image_url=url + '/detail-pets.png'
                        )
                    ]
                )
            )

        # ---- 交通|周邊景點 子選項 ----
        elif data == 'action=transfer':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="這是接送服務的詳細介紹")]
                )
            )
        elif data == 'action=turtle_island':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="這是接送服務的詳細介紹")]
                )
            )
        elif data == 'action=old_street':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="這是接送服務的詳細介紹")]
                )
            )

if __name__ == "__main__":
    app.run()