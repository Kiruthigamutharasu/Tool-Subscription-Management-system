memory_store = {}

def get_context(user_id):
    return memory_store.get(user_id, [])

def add_message(user_id, message):
    if user_id not in memory_store:
        memory_store[user_id] = []
    memory_store[user_id].append(message)