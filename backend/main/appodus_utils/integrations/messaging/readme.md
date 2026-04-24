# Examples:

## 1. Standard Text Messages (SMS/Email)

### SMS Example

<pre> ```python

sms_response = await messaging_service.send_message(
    MessageRequest(
        channel="sms",
        recipient="+1234567890",
        context={"text": "Your verification code is 123456"},
        extras={
            "campaign": "user_verification",
            "priority": "high"
        }
    )
)

``` </pre>
### Email Example

<pre> ```python

email_response = await messaging_service.send_message(
    MessageRequest(
        channel="email",
        recipient="user@example.com",
        template_name="welcome_email",
        context={
            "user_name": "John Doe",
            "activation_link": "https://example.com/activate/123"
        },
        extras={
            "user_id": "123",
            "email_type": "onboarding"
        }
    )
)

``` </pre>

## 2. WhatsApp Messages

### WhatsApp Text Message

<pre> ```python

whatsapp_text_response = await messaging_service.send_whatsapp_message(
    WhatsAppMessageRequest(
        recipient="1234567890",
        message_type="text",
        text="Hello! Your order #12345 has shipped.",
        extras={"order_id": "12345"}
    )
)

``` </pre>

### WhatsApp Template Message

<pre> ```python

whatsapp_template_response = await messaging_service.send_whatsapp_message(
    WhatsAppMessageRequest(
        recipient="1234567890",
        message_type="template",
        template_name="order_shipped",
        language_code="en_US",
        components=[
            {
                "type": "body",
                "parameters": ["12345", "John Doe"]
            }
        ]
    )
)

``` </pre>

### WhatsApp Media Message (Image)

<pre> ```python

whatsapp_media_response = await messaging_service.send_whatsapp_media(
    recipient="1234567890",
    media=WhatsAppMedia(
        link="https://example.com/products/123.jpg",
        caption="Your ordered product"
    ),
    media_type="image",
    extras={"order_id": "12345"}
)

``` </pre>

### WhatsApp Interactive Buttons

<pre> ```python

whatsapp_interactive_response = await messaging_service.send_whatsapp_interactive(
    recipient="1234567890",
    interactive=WhatsAppInteractive(
        type="button",
        body={"text": "Rate your recent experience"},
        footer={"text": "Reply with your feedback"},
        action=WhatsAppInteractiveAction(
            buttons=[
                WhatsAppButton(
                    type="reply",
                    title="👍 Good",
                    payload="feedback_good"
                ),
                WhatsAppButton(
                    type="reply",
                    title="👎 Poor",
                    payload="feedback_poor"
                )
            ]
        )
    )
)

``` </pre>

## 3. Push Notifications

### 1. iOS/Android Push Notification

<pre> ```python

push_response = await messaging_service.send_push_notification(
    recipient=PushNotificationRecipient(
        device_tokens=["device_token_ios123"],
        platform="ios",
        user_id="user_123"
    ),
    payload=PushNotificationPayload(
        title="New Message",
        body="You have 3 new notifications",
        data={
            "message_id": "123",
            "type": "inbox"
        },
        image_url="https://example.com/notifications/alert.png"
    ),
    extras={"campaign": "user_engagement"}
)

``` </pre>

### 2. Web Push Notification

<pre> ```python

web_push_response = await messaging_service.send_push_notification(
    recipient=PushNotificationRecipient(
        platform="web",
        web_push_subscription={
            "endpoint": "https://fcm.googleapis.com/...",
            "keys": {
                "auth": "auth_key_here",
                "p256dh": "p256dh_key_here"
            }
        },
        user_id="user_123"
    ),
    payload=WebPushNotification(
        title="New Message",
        body="You have a new chat message",
        icon="/icons/icon-192x192.png",
        actions=[
            {
                "action": "view",
                "title": "View Message"
            },
            {
                "action": "dismiss",
                "title": "Dismiss"
            }
        ],
        data={
            "url": "/chat/123",
            "message_id": "123"
        }
    ),
    extras={
        "campaign": "web_push",
        "page_url": "/chat"
    }
)

``` </pre>

## 4. Bulk Message Examples

### Bulk SMS

<pre> ```python

bulk_sms_response = await messaging_service.send_bulk_messages([
    MessageRequest(
        channel="sms",
        recipient="+1234567890",
        context={"text": "Your appointment is tomorrow at 10AM"}
    ),
    MessageRequest(
        channel="sms",
        recipient="+1987654321",
        context={"text": "Your prescription is ready for pickup"}
    )
])

``` </pre>

### Bulk WhatsApp Media

<pre> ```python

bulk_whatsapp_media = await messaging_service.send_bulk_whatsapp_media(
    BulkWhatsAppMediaRequest(
        requests=[
            {
                "recipient": "1234567890",
                "media": WhatsAppMedia(link="https://example.com/catalog/1.jpg"),
                "caption": "New product in stock"
            },
            {
                "recipient": "9876543210",
                "media": WhatsAppMedia(link="https://example.com/catalog/2.jpg"),
                "caption": "Special offer just for you"
            }
        ],
        extras={"campaign": "product_launch"}
    )
)

``` </pre>

### Bulk Push Notifications

#### 1. Mobile

<pre> ```python

bulk_push_response = await messaging_service.send_bulk_push_notifications(
    BulkPushNotificationRequest(
        requests=[
            PushNotificationRequest(
                recipient=PushNotificationRecipient(
                    device_tokens=["token_android_123"],
                    platform="android"
                ),
                payload=PushNotificationPayload(
                    title="Security Alert",
                    body="New login detected from Chrome browser"
                )
            ),
            PushNotificationRequest(
                recipient=PushNotificationRecipient(
                    device_tokens=["token_ios_456"],
                    platform="ios"
                ),
                payload=PushNotificationPayload(
                    title="Security Alert",
                    body="New login detected from Safari browser"
                )
            )
        ]
    )
)

``` </pre>

#### 2. Web

<pre> ```python

bulk_web_push = await messaging_service.send_bulk_push_notifications(
    BulkPushNotificationRequest(
        requests=[
            PushNotificationRequest(
                recipient=PushNotificationRecipient(
                    platform="web",
                    web_push_subscription=web_subscription_1,
                    user_id="user_123"
                ),
                payload=WebPushNotification(...)
            ),
            PushNotificationRequest(
                recipient=PushNotificationRecipient(
                    platform="web",
                    web_push_subscription=web_subscription_2,
                    user_id="user_456"
                ),
                payload=WebPushNotification(...)
            )
        ]
    )
)

``` </pre>

#### 3. Mixed mobile and web

<pre> ```python

mixed_push = await messaging_service.send_bulk_push_notifications(
    BulkPushNotificationRequest(
        requests=[
            # Web push
            PushNotificationRequest(
                recipient=PushNotificationRecipient(
                    platform="web",
                    web_push_subscription=web_subscription_1
                ),
                payload=WebPushNotification(...)
            ),
            # Mobile push
            PushNotificationRequest(
                recipient=PushNotificationRecipient(
                    platform="ios",
                    device_tokens=["ios_device_token"]
                ),
                payload=PushNotificationPayload(...)
            )
        ]
    )
)

``` </pre>

## 5. Advanced WhatsApp Examples

### WhatsApp Product Message

<pre> ```python

whatsapp_product_response = await messaging_service.send_whatsapp_interactive(
    recipient="1234567890",
    interactive=WhatsAppInteractive(
        type="product",
        body={"text": "You might like this product:"},
        action=WhatsAppInteractiveAction(
            catalog_id="SHOP123",
            product_retailer_id="PROD456"
        )
    ),
    extras={"product_campaign": "summer_sale"}
)

``` </pre>

### WhatsApp List Message

<pre> ```python

whatsapp_list_response = await messaging_service.send_whatsapp_interactive(
    recipient="1234567890",
    interactive=WhatsAppInteractive(
        type="list",
        body={"text": "Choose delivery option:"},
        action=WhatsAppInteractiveAction(
            button="Delivery Options",
            sections=[
                WhatsAppSection(
                    title="Standard",
                    rows=[
                        WhatsAppSectionRow(
                            id="delivery_std",
                            title="Standard (3-5 days)",
                            description="$5.99"
                        )
                    ]
                ),
                WhatsAppSection(
                    title="Express",
                    rows=[
                        WhatsAppSectionRow(
                            id="delivery_exp",
                            title="Express (1-2 days)",
                            description="$12.99"
                        )
                    ]
                )
            ]
        )
    )
)

``` </pre>

## 6. Message with Priority Handling

### High Priority SMS (e.g., OTP)

<pre> ```python

high_priority_response = await messaging_service.send_message(
    MessageRequest(
        channel="sms",
        recipient="+1234567890",
        context={"text": "Your OTP is 987654 - valid for 5 minutes"},
        priority="high",
        extras={
            "message_type": "otp",
            "expires_at": "2023-07-15T12:00:00Z"
        }
    )
)

``` </pre>

## 7. Full Message with All Features

### Comprehensive example with all features

<pre> ```python

comprehensive_response = await messaging_service.send_message(
    MessageRequest(
        channel="whatsapp",
        recipient="1234567890",
        template_name="order_confirmation",
        context={
            "order_number": "12345",
            "customer_name": "John Doe",
            "delivery_date": "July 20, 2023"
        },
        priority="high",
        extras={
            "order_id": "12345",
            "customer_id": "789",
            "campaign": "post_purchase",
            "trace_id": "abc123xyz"
        }
    )
)

``` </pre>