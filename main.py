import telebot
import requests
import jsons
from Class_ModelResponse import ModelResponse

# Замените 'YOUR_BOT_TOKEN' на ваш токен от BotFather
API_TOKEN = '8530600992:AAHRUjglzqiJsr7Q2J2XghTEi9t7aBy_Q10'
bot = telebot.TeleBot(API_TOKEN)

# Словарь для хранения контекста пользователей
# Ключ: user_id (int), Значение: список сообщений (list of dict)
user_contexts = {}

def get_user_context(user_id):
    """Получить или создать контекст для пользователя"""
    if user_id not in user_contexts:
        # Создаем новый контекст с системным сообщением
        user_contexts[user_id] = [
            {
                "role": "system",
                "content": "Ты полезный AI-ассистент. Отвечай вежливо и по делу, учитывая контекст разговора."
            }
        ]
    return user_contexts[user_id]

def clear_user_context(user_id):
    """Очистить контекст пользователя (оставить только системное сообщение)"""
    if user_id in user_contexts:
        user_contexts[user_id] = [user_contexts[user_id][0]]

def add_user_message(user_id, message):
    """Добавить сообщение пользователя в контекст"""
    context = get_user_context(user_id)
    context.append({
        "role": "user",
        "content": message
    })
    
    # Ограничиваем длину контекста (последние 20 сообщений + системное)
    if len(context) > 21:  # 1 системное + 20 сообщений
        context = [context[0]] + context[-20:]
        user_contexts[user_id] = context

def add_assistant_message(user_id, message):
    """Добавить ответ ассистента в контекст"""
    context = get_user_context(user_id)
    context.append({
        "role": "assistant",
        "content": message
    })

def check_lm_studio_connection():
    """Проверить подключение к LM Studio"""
    try:
        response = requests.get('http://localhost:1234/v1/models', timeout=5)
        return response.status_code == 200
    except:
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Привет! Я ваш Telegram бот с поддержкой контекста.\n"
        "Я помню историю нашего разговора и могу отвечать на вопросы с учетом предыдущих сообщений.\n\n"
        "Доступные команды:\n"
        "/start - вывод всех доступных команд\n"
        "/model - информация о используемой модели\n"
        "/context - показать текущую длину контекста\n"
        "/clear - очистить историю диалога\n\n"
        "Просто отправьте сообщение, и я отвечу с учетом нашего разговора!"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['model'])
def send_model_name(message):
    """Информация о используемой модели"""
    if not check_lm_studio_connection():
        bot.reply_to(message, "❌ LM Studio не подключен")
        return
        
    try:
        response = requests.get('http://localhost:1234/v1/models', timeout=5)
        if response.status_code == 200:
            model_info = response.json()
            model_name = model_info['data'][0]['id']
            bot.reply_to(message, f"🤖 Используемая модель: {model_name}")
        else:
            bot.reply_to(message, '❌ Не удалось получить информацию о модели.')
    except Exception as e:
        bot.reply_to(message, f'❌ Ошибка при запросе к LM Studio: {str(e)}')

@bot.message_handler(commands=['context'])
def show_context_length(message):
    """Показать текущую длину контекста"""
    user_id = message.from_user.id
    context = get_user_context(user_id)
    context_length = len(context) - 1  # Минус системное сообщение
    
    if context_length == 0:
        bot.reply_to(message, "📝 История диалога пуста. Начните разговор!")
    else:
        messages_count = context_length // 2  # Каждое сообщение пользователя + ответ
        bot.reply_to(message, f"📝 Текущая длина контекста: {context_length} сообщений ({messages_count} пар вопрос-ответ)")

@bot.message_handler(commands=['clear'])
def clear_context(message):
    """Очистить историю диалога для пользователя"""
    user_id = message.from_user.id
    clear_user_context(user_id)
    bot.reply_to(message, "🧹 История диалога очищена! Начинаем новый разговор.")

@bot.message_handler(func=lambda message: message.text.startswith('/'))
def handle_unknown_command(message):
    """Обработка неизвестных команд"""
    bot.reply_to(message, "❌ Неизвестная команда. Используйте /start для просмотра доступных команд.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Обработка текстовых сообщений с учетом контекста"""
    # Пропускаем команды
    if message.text.startswith('/'):
        return
    
    user_id = message.from_user.id
    user_message = message.text
    
    if not check_lm_studio_connection():
        bot.reply_to(message, "❌ LM Studio не подключен. Запустите LM Studio, загрузите модель и нажмите 'Start Server'")
        return
    
    add_user_message(user_id, user_message)
    
    context = get_user_context(user_id)
    
    request_data = {
        "messages": context,
        "temperature": 0.7,
        "max_tokens": 500,
        "stop": ["</s>"]
    }
    
    try:
        response = requests.post(
            'http://localhost:1234/v1/chat/completions',
            json=request_data,
            timeout=30
        )

        if response.status_code == 200:
            model_response = jsons.loads(response.text, ModelResponse)
            bot_reply = model_response.choices[0].message.content
            
            add_assistant_message(user_id, bot_reply)
            
            bot.reply_to(message, bot_reply)
        else:
            context = get_user_context(user_id)
            if len(context) > 1 and context[-1]["role"] == "user":
                context.pop()
                user_contexts[user_id] = context
            
            bot.reply_to(message, f'❌ Ошибка модели: {response.status_code}')
            
    except requests.exceptions.ConnectionError:
        context = get_user_context(user_id)
        if len(context) > 1 and context[-1]["role"] == "user":
            context.pop()
            user_contexts[user_id] = context
            
        bot.reply_to(message, "❌ Не удалось подключиться к LM Studio")
    except requests.exceptions.Timeout:
        context = get_user_context(user_id)
        if len(context) > 1 and context[-1]["role"] == "user":
            context.pop()
            user_contexts[user_id] = context
            
        bot.reply_to(message, "⏰ Таймаут при обращении к модели")
    except Exception as e:
        context = get_user_context(user_id)
        if len(context) > 1 and context[-1]["role"] == "user":
            context.pop()
            user_contexts[user_id] = context
            
        bot.reply_to(message, f'❌ Непредвиденная ошибка: {str(e)}')

# Запуск бота
if __name__ == '__main__':
    print("🤖 Бот с поддержкой контекста запускается...")
    if check_lm_studio_connection():
        print("✅ LM Studio подключен")
    else:
        print("❌ LM Studio не подключен")
    
    print("✅ Бот готов к работе!")
    print("📝 Система контекста активирована")
    bot.polling(none_stop=True)