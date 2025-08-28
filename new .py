    def select_store(store_number):

    # Get the selected type from the previous action

    selected_type = user_actions[-1].get("selected_option", button_names[0])



    # Store the selected store number in user actions

    user_actions[-1]["store_number"] = store_number



    # Map selected type to numeric value for display

    type_mapping = {

        "Cutting": "1",

        "Carcas": "2",

        "Check": "3"

    }

    type_value = type_mapping.get(selected_type, "1")



    # Get a fresh weight from serial before sending to API

    fresh_weight = read_weight_from_serial()

    print(fresh_weight)

    if fresh_weight:

        weight_to_send = str(fresh_weight)

    else:

        weight_to_send = str(weight_value)  # fallback to last known value



     # Prepare API parameters

    api_url = f"http://shatat-ue.runasp.net/api/Devices/ScanForDevice2?weight={weight_to_send}&TypeOfCow={type_value}&TechId=2335C4B&MachId=1&storeId={store_number}"

    print(api_url)

    # Send data to API using POST with no body, params in URL

    try:

        response = requests.post(api_url, timeout=15)

        print(response.text)

        if response.headers.get('Content-Type', '').startswith('application/json'):

            api_response = response.json()

        else:

            api_response = {

                "statusCode": response.status_code,

                "message": response.text

            }

    except Exception as e:

        api_response = {

            "statusCode": 500,

            "message": str(e)

        }



    # Create data that would be sent to API (for display)

    data_to_send = {

        "type": selected_type,

        "type_value": type_value,

        "store": store_number,

        "weight": weight_to_send,

        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")

    }



    # Print data being sent

    print("Data being sent:")

    print(data_to_send)



    # Process API response message

    extracted_number = None

    if "statusCode" in api_response and api_response["statusCode"] == 200:

        raw_message = api_response.get("message", "")



        if raw_message.startswith("OK1 "):

            raw_message = raw_message[4:]  # remove "OK1 "



        message_list = raw_message.split(",")

        print("Raw split message list:", message_list)



        # Remove 'Z' from the first element

        if len(message_list) > 0 and message_list[0].startswith("Z"):

            message_list[0] = message_list[0][1:]



        # Remove 'L' from the last element (the date)

        if len(message_list) > 0 and message_list[-1].endswith("L"):

            message_list[-1] = message_list[-1][:-1]



        # Extract number only from Arabic part if exists

        if len(message_list) > 6:

            arabic_text = message_list[6]

            match = re.search(r'\d+', arabic_text)

            if match:

                extracted_number = match.group(0)

                message_list[6] = extracted_number



        print("Processed message list:")

        print(message_list)



        if extracted_number:

            print("Extracted number from Arabic text:", extracted_number)

    else:

        print("API response error or unexpected format:")

        print(api_response)







    def crop_white_left(image):

    img_array = np.array(image)

    nonwhite = np.where(img_array == 0)

    if nonwhite[1].size:

        left = nonwhite[1].min()

        cropped = image.crop((left, 0, image.width, image.height))

        return cropped

    else:

        return image



    def load_and_prepare_image(path):

    image = Image.open(path).convert('1')

    image = crop_white_left(image)

    width, height = image.size

    if width % 8 != 0:

        padded_width = ((width + 7) // 8) * 8

        new_image = Image.new('1', (padded_width, height), 1)

        new_image.paste(image, (0, 0))

        image = new_image

        width = padded_width

    width_bytes = width // 8

    data = image.tobytes()

    return width_bytes, height, data



    def send_tspl_command(printer, command):

    if printer.is_kernel_driver_active(0):

        printer.detach_kernel_driver(0)

    printer.set_configuration()

    endpoint = printer[0][(0,0)][0]

    printer.write(endpoint.bEndpointAddress, command)

    print("Command sent successfully!")



    def send_multi_bmp_to_printer(printer, bmp_paths_and_coords, extra_text=None):

    command_prefix = (

        f"SIZE 50 mm, 40 mm\r\n"

        "GAP 2 mm, 0 mm\r\n"

        "DENSITY 10\r\n"

        "SPEED 6\r\n"

        "DIRECTION 1\r\n"

        "REFERENCE 0,0\r\n"

        "CLS\r\n"

    )



    # Add any extra text if provided

    if extra_text:

        command_prefix += extra_text



    command = command_prefix.encode('ascii')



    for bmp_path, (x, y) in bmp_paths_and_coords:

        width_bytes, height, data = load_and_prepare_image(bmp_path)

        bmp_cmd = f"BITMAP {x},{y},{width_bytes},{height},0,".encode('ascii')

        command += bmp_cmd + data



    print_cmd = b"\r\nPRINT 2\r\n"

    full_command = command + print_cmd

    send_tspl_command(printer, full_command)



    # Example parts list

    meat_parts = [

    "left shoulder",

    "left thigh",

    "right shoulder",

    "right thigh"

    ]



    # Build per selection

    def print_part_by_index(printer, index):

    if index < 1 or index > len(meat_parts):

        print("Out of range!")

        return

    part = meat_parts[index-1]

    # Add multi-image support here:

    bmp_jobs = [

        (f"{part}.bmp", (70, 205)),           # Main image

        # ...add more here if you need for this label

    ]

    # Any extra text?

    extra_text = (

        f'TEXT 0,0,"2",0,1,1,"{message_list[1]}"\r\n'

        f'TEXT 0,30,"2",0,1,1,"{message_list[2]}"\r\n'

        f'TEXT 0,60,"2",0,1,1,"order number:{message_list[4]}"\r\n'

        f'TEXT 0,90,"2",0,1,1,"batch number:{message_list[3]}"\r\n'

        f'TEXT 0,120,"2",0,1,1,"Date: {message_list[8]}"\r\n'

        f'TEXT 0,150,"2",0,1,1,"weight:{message_list[7]}"\r\n'

        f'TEXT 30,220,"2",0,1,1,"{message_list[6]}"\r\n'

        f'QRCODE 260,120,L,7,A,0,"{message_list[0]}"\r\n'

        f'TEXT 280,280,"2",0,1,1,"{message_list[0]}"\r\n'

         )       



    send_multi_bmp_to_printer(printer, bmp_jobs, extra_text)



    printer = usb.core.find(idVendor=0x2D37, idProduct=0xDEF4)

    if printer:

    index = int(extracted_number)

    print_part_by_index(printer, index)

    printer.reset()  # Attempt a soft reset to clear any potential issues



    else:

    print("Printer not found.")