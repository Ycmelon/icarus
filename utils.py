def parse_history(chat_log):
    history = []

    curr_message_id = None
    curr_user = "user"
    curr_user_msg = []
    curr_bot_msg = []
    for i in chat_log:
        # if bot->user, a piece of history just ended
        if curr_user == "bot" and i[0] == "user":
            # so append it to history
            history.append(
                {
                    "id": curr_message_id,
                    "input": "\n".join(curr_user_msg),
                    "response": "\n".join(curr_bot_msg),
                }
            )

            # reset variables
            curr_message_id = None
            curr_user_msg.clear()
            curr_bot_msg.clear()

        curr_user = i[0]  # update curr user

        # set message id if need
        if curr_message_id == None:
            curr_message_id = i[2]

        # then, append appropriately
        if curr_user == "user":
            curr_user_msg.append(i[1])
        else:
            curr_bot_msg.append(i[1])

    if curr_message_id != None:  # if there is a remaining message
        history.append(  # add it
            {
                "id": curr_message_id,
                "input": "\n".join(curr_user_msg),
                "response": "\n".join(curr_bot_msg),
            }
        )

    return history
