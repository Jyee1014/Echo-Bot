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
    MessageAction,
    # Rich的都是導覽
    RichMenuSize,
    RichMenuRequest,
    RichMenuArea,
    RichMenuBounds,
    # Flex的都是導覽
    FlexMessage,
    FlexContainer,
    FlexCarousel,
    FlexBubble,
    FlexImage,
    FlexBox,
    FlexText,
    FlexIcon
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
        # (餐飲|環境介紹 / 入住須知 / 位置|周邊景點).
        body = {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "導覽",
            "chatBarText": "導覽",
            "areas": [
                {
                    "bounds": {"x": 67, "y": 67, "width": 600, "height": 200},
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
                    "action": {"type": "message", "text": "位置|周邊景點"}
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

        # -------------------------------------------------------------
        # Rich menu actions
        # -------------------------------------------------------------

        # 線上訂房 完成
        if text == '線上訂房':
            booking_buttons_template = ButtonsTemplate(
                thumbnail_image_url=url + '/background.jpg',
                title='線上訂房',
                text='請選擇您想查看的方案',
                actions=[
                    PostbackAction(label='單間價格', data='action=room_price'),
                    PostbackAction(label='包棟價格', data='action=whole_house_price'),
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TemplateMessage(alt_text='線上訂房', template=booking_buttons_template)]
                )
            )

        # 客房導覽 待确认
        elif text == '客房導覽':
            room_tour_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/room-twin.jpg',
                        action=PostbackAction(label='雙人房', data='action=room_twin')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/room-four.jpg',
                        action=PostbackAction(label='四人房', data='action=room_four')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/room-family.jpg',
                        action=PostbackAction(label='親子房', data='action=room_family')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/room-bathroom.jpg',
                        action=PostbackAction(label='衛浴', data='action=room_bathroom')
                    ),
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TemplateMessage(alt_text='客房導覽', template=room_tour_template)]
                )
            )

        # 餐飲|環境介紹 完成
        elif text == '餐飲|環境介紹':
            dining_env_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/dining-bigpic.jpg',
                        action=PostbackAction(label='餐飲', data='action=dining')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/environment-bigpic.jpg',
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
                        image_url=url + '/check-in-guide.png',
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

        # 交通|周邊景點 完成
        elif text == '位置|周邊景點':
            location_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/location-bigpic.png',
                        action=PostbackAction(label='位置', data='action=location')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/attraction-bigpic.png',
                        action=PostbackAction(label='周邊景點', data='action=attractions')
                    ),
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TemplateMessage(alt_text='位置周邊景點', template=location_template)]
                )
            )


# Postback
@line_handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        url = get_static_url()

        if data == 'action=room_price':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/booking-price-room.jpg',
                            preview_image_url=url + '/booking-price-room.jpg'
                        ),
                        TextMessage(text="📞 0986-040-310\n"
                                         "✉️ chancevilla262@gmail.com\n"
                                         "📍 宜蘭縣礁溪鄉武暖路45-5號\n\n"
                                         "春秧綠、夏荷香、秋稻浪、冬暖陽——四時蒔裳，皆有秝景。🌾\n"
                                         "歡迎信息我們，預約入住！")
                    ]
                )
            )

        elif data == 'action=whole_house_price':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/booking-price-whole.jpg',
                            preview_image_url=url + '/booking-price-whole.jpg'
                        ),
                        TextMessage(text="📞 0986-040-310\n"
                                         "✉️ chancevilla262@gmail.com\n"
                                         "📍 宜蘭縣礁溪鄉武暖路45-5號\n\n"
                                         "春秧綠、夏荷香、秋稻浪、冬暖陽——四時蒔裳，皆有秝景。🌾\n"
                                         "歡迎信息我們，預約入住！")
                    ]
                )
            )
            
        # ---- 客房導覽 子選項 ----
        elif data == 'action=room_twin':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-room-twin.jpg',
                            preview_image_url=url + '/detail-room-twin.jpg'
                        ),
                        TextMessage(text="雙人房選用1張Queen Size雙人床，帶給您一夜好眠。\n"
                                         "各項房內設備、備品及住宿須知，已完整整理於下方導覽選單的「入住須知」中，歡迎隨時點閱。")
                    ]
                )
            )
        elif data == 'action=room_four':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-room-four.jpg',
                            preview_image_url=url + '/detail-room-four.jpg'
                        ),
                        TextMessage(text="四人房內配置2張舒適的Queen Size雙人床，寬敞空間適合家庭或好友同住。\n"
                                         "更多房內設施與貼心服務，歡迎點選導覽選單中的「入住須知」詳細查閱。")
                    ]
                )
            )
        elif data == 'action=room_family':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-room-family.jpg',
                            preview_image_url=url + '/detail-room-family.jpg'
                        ),
                        TextMessage(text="親子房內配置兩張Queen Size雙人床及一張專屬兒童床，貼心設計讓全家出遊更輕鬆。\n"
                                         "更多房內設施與親子友善服務，歡迎點選導覽選單中的「入住須知」詳細查閱。")
                    ]
                )
            )
        elif data == 'action=room_bathroom':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-room-bathroom.jpg',
                            preview_image_url=url + '/detail-room-bathroom.jpg'
                        ),
                        TextMessage(text="衛浴空間舒適潔淨，為您提供優質的盥洗體驗。\n"
                                         "各項衛浴設備、備品內容及環保政策（不主動提供一次性用品），已完整整理於導覽選單的「入住須知」中，歡迎隨時點閱。")
                    ]
                )
            )

        # ---- 餐飲|環境介紹 子選項 ----
        elif data == 'action=dining':
            dining_carousel_template = ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url=url + '/breakfast.jpg',
                        action=PostbackAction(
                            label='早餐',
                            data='action=breakfast',
                            display_text='早餐')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/8bq-logo.png',
                        action=PostbackAction(
                            label='| 代訂食材 | 烤友社',
                            data='action=eightbq',
                            display_text='| 代訂食材 | 烤友社')
                    ),
                    ImageCarouselColumn(
                        image_url=url + '/flameduck-logo.jpg',
                        action=PostbackAction(
                            label='火焰夯鴨',
                            data='action=flameduck',
                            display_text='火焰夯鴨')
                    )
                ]
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TemplateMessage(alt_text='餐飲介紹', template=dining_carousel_template)]
                )
            )
        elif data == 'action=breakfast':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-breakfast.png',
                            preview_image_url=url + '/detail-breakfast.png'
                        ),
                        TextMessage(text="每天都有不同的早餐驚喜！\n☀️新鮮現做、營養均衡，是一天活力的開始。\n\n"
                                          "我們每日提供營養均衡的早餐，內容包含主食、蛋白質、時蔬、水果及飲品，"
                                          "讓您補充一天所需的能量。\n早餐內容每日隨機搭配，依照當日食材與供應情況調整，"
                                          "每一天都能享受不同的美味與驚喜！")
                    ]
                )
            )
        elif data == 'action=eightbq':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-8bq-1.jpg',
                            preview_image_url=url + '/detail-8bq-1.jpg'
                        ),
                        ImageMessage(
                            original_content_url=url + '/detail-8bq-2.jpg',
                            preview_image_url=url + '/detail-8bq-2.jpg'
                        ),
                        TextMessage(text="🍖 烤友社｜代訂食材服務"
                                          "\n\n想輕鬆享受烤肉時光嗎？\n如需代訂烤肉食材，請於入住前 7 天與客服聯繫並完成預訂。"
                                          "\n\n🔥 烤肉設備\n提供 1 台美式烤肉架\n僅提供烤肉盤，其餘耗材（如木炭、夾子、烤網、鋁箔紙、紙盤、餐具等）請自行準備。\n若使用代訂食材服務，代訂廠商將提供基本耗材\n使用烤肉場地將酌收 清潔費 NT$2,000。"
                                          "\n\n🍲 火鍋設備\n交誼廳提供 瓦斯爐供使用。\n使用火鍋設備不另收清潔費。"
                                          "\n\n💬 如有任何疑問或代訂需求，歡迎提前與客服聯繫，我們將竭誠為您服務！"
                        )
                    ]
                )
            )
        elif data == 'action=flameduck':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-flameduck-1.jpg',
                            preview_image_url=url + '/detail-flameduck-1.jpg'
                        ),
                        ImageMessage(
                            original_content_url=url + '/detail-flameduck-2.jpg',
                            preview_image_url=url + '/detail-flameduck-2.jpg'
                        ),
                        ImageMessage(
                            original_content_url=url + '/detail-flameduck-3.jpg',
                            preview_image_url=url + '/detail-flameduck-3.jpg'
                        ),
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

        # ---- 交通|周邊景點 子選項 ---- 完成
        elif data == 'action=location':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        LocationMessage(
                            title='蒔裳秝景',
                            address="26245宜蘭縣礁溪鄉武暖路45-5號",
                            latitude=24.781609811337216,
                            longitude=121.76645135904401
                        )
                    ]
                )
            )
        elif data == 'action=attractions':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(
                            original_content_url=url + '/detail-attraction.png',
                            preview_image_url=url + '/detail-attraction.png'
                        )
                    ]
                )
            )

if __name__ == "__main__":
    app.run()