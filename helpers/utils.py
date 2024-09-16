import random
import string
import pytz
from typing import Optional
from babel.dates import format_date
from rasa_sdk.executor import CollectingDispatcher
from typing import Dict, Text, Any, List, Tuple
import logging 
import requests
from datetime import datetime, timedelta
import dateparser


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def confirm_user(cpf_user):
    url = f"http://localhost:3010/usuario/consulta/{cpf_user}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            logger.info(f"User validation successful")
        else:
            logger.warning(f"User validation failed with status code {response.status_code}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to user validation service for CPF {cpf_user}: {e}")
        return False
        
def validate_cpf_value(slot_value: Any,
        dispatcher: CollectingDispatcher,
        ) -> Dict[Text,Any]:
    
    slot_value = ''.join(filter(str.isdigit, slot_value))

    if len(slot_value) != 11:
        dispatcher.utter_message(text="CPF deve conter 11 digitos")
        return {"cpf": None}

    if slot_value == slot_value[0] * 11:
        dispatcher.utter_message(text="CPF Inválido")
        return {"cpf": None}

    sum1 = sum(int(slot_value[i]) * (10 - i) for i in range(9))
    first_digit = 11 - (sum1 % 11)
    first_digit = 0 if first_digit >= 10 else first_digit

    sum2 = sum(int(slot_value[i]) * (11 - i) for i in range(9)) + first_digit * 2
    second_digit = 11 - (sum2 % 11)
    second_digit = 0 if second_digit >= 10 else second_digit

    if first_digit == int(slot_value[9]) and second_digit == int(slot_value[10]):
        return {"cpf": slot_value}
    else:
        dispatcher.utter_message(text="CPF Inválido")
        return {"cpf": None}

        
def validate_cpf_bd(
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        ) -> Dict[Text,Any]:
    try:
        if confirm_user(slot_value):  
            return {"cpf" : slot_value}
        else:
            dispatcher.utter_message("Parece que você não está cadastrado.")
            logger.warning(f"CPF validation failed for {slot_value}. CPF not found.")
            return {"cpf" : None,}
    except Exception as e:
        dispatcher.utter_message("Não conseguimos validar seu CPF")
        logger.error(f"Error during CPF validation for {slot_value}: {str(e)}")
        return {"cpf" : None}
    
    
def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

def get_event_id_from_cpf(cpf_user):
    url_get = f"http://localhost:3010/agendamentos/{cpf_user}"
    try:
        response_get = requests.get(url_get)
        if response_get.status_code == 200:
            data = response_get.json()
            events = data.get('agendamentos', [])
            if events:
                return events[0].get('codAgendamento'), None
            else:
                logger.info("No events found")
                return None, "Nenhum evento encontrado para o CPF fornecido."
        else:
            logger.error("Error retrieving event")
            return None, "Erro ao recuperar o evento."
    except Exception as e:
        logger.error(f"Failed to retrieve events for user {cpf_user}: {str(e)}")
        return None, f"Erro ao recuperar os eventos: {str(e)}"

    
#funcao que faz a busca dos proximos 5 horarios livres, comecando a partir das 7 horas, com intervalo de 1 hora
def find_next_free_slots(api_url: str, max_slots=5):

    timezone = pytz.timezone('America/Sao_Paulo')
    current_time = (datetime.now(tz=timezone) + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
    free_slots = []

    while len(free_slots) < max_slots:
        start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        last_end_time = start_of_day + timedelta(hours=7)  

        try:
            response = requests.get(api_url + f'?dataInicial={start_of_day.isoformat()}&dataFinal={end_of_day.isoformat()}')
            response.raise_for_status()
            events_result = response.json()
            events = events_result.get('eventos', [])
        except Exception as e:
            print(f"Failed to fetch events: {str(e)}")
            break

        if not events:
            while last_end_time < end_of_day and last_end_time.hour < 18 and len(free_slots) < max_slots:
                free_slots.append(last_end_time.strftime('%d/%m %H:%M'))
                last_end_time += timedelta(hours=1)
        else:
            for event in events:
                start_event = datetime.fromisoformat(event['dataInicial'].replace("Z", "+00:00")).astimezone(timezone)
                end_event = datetime.fromisoformat(event['dataFinal'].replace("Z", "+00:00")).astimezone(timezone)

                while last_end_time < start_event and last_end_time.hour < 18 and len(free_slots) < max_slots:
                    free_slots.append(last_end_time.strftime('%d/%m %H:%M'))
                    last_end_time += timedelta(hours=1)
                last_end_time = max(last_end_time, end_event)

            while last_end_time < end_of_day and last_end_time.hour < 18 and len(free_slots) < max_slots:
                free_slots.append(last_end_time.strftime('%d/%m %H:%M'))
                last_end_time += timedelta(hours=1)

        current_time = end_of_day

    return free_slots[:max_slots]





def modify_event(event_id: str, start_time: str, end_time: str) -> bool:
    url = f"http://localhost:3010/agendamento/atualizar/{event_id}"  
    data = {
        "dataInicial": start_time,
        "dataFinal": end_time
    }
    
    try:
        response = requests.put(url, json=data)
        response.raise_for_status()  
        

        logger.info(f'Evento atualizado com sucesso: {response.json()}') 
        return True

    except requests.exceptions.RequestException as error:
        logger.error(f'Ocorreu um erro ao atualizar o evento {event_id}: {error}')
        return False



def normalize_date(slot_value: str, dispatcher: CollectingDispatcher) -> Optional[datetime]:
    target_date = dateparser.parse(
        slot_value,
        settings={
            'TIMEZONE': 'America/Sao_Paulo',
            'RETURN_AS_TIMEZONE_AWARE': True
        }
    )
    if target_date is None:
        dispatcher.utter_message(text="Não consegui entender a data: " + slot_value)
        logger.info("Error in date.")
        return None

    return target_date


def check_availability(date: datetime, dispatcher: CollectingDispatcher, api_url: str) -> Tuple[bool, List[str]]:
    # Make current_date timezone-aware using date's timezone
    current_datetime = datetime.now(tz=date.tzinfo)
    current_date = current_datetime.date()
    date_only = date.date()
    if date_only < current_date:
        date = current_datetime

    available_slots = []
    num_slots_needed = 5  

    while len(available_slots) < num_slots_needed:
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            events_result = response.json()
            events = events_result.get('eventos', [])
            logger.debug(f"Retrieved events for {date.strftime('%Y-%m-%d')}")
        except Exception as e:
            logger.error(f"Error retrieving events for {date.strftime('%Y-%m-%d')}: {str(e)}")
            dispatcher.utter_message(text="Erro ao recuperar eventos do calendário.")
            return False, []

        daily_slots = []
        # Adjust starting hour
        if date_only == current_date:
            # Today
            start_hour = current_datetime.hour + 1  # Start from one hour ahead
            if start_hour < 7:
                start_hour = 7  # Ensure starting hour is at least 7
            elif start_hour >= 18:
                # No slots available today
                date += timedelta(days=1)
                date_only = date.date()
                continue  # Proceed to next day
        else:
            start_hour = 7  # Start from 7 am for future dates

        for hour in range(start_hour, 18):
            if len(available_slots) >= num_slots_needed:
                break
            check_time = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            is_free = True
            for event in events:
                event_start = datetime.fromisoformat(event['dataInicial'].replace("Z", "+00:00"))
                event_end = datetime.fromisoformat(event['dataFinal'].replace("Z", "+00:00"))
                if event_start <= check_time < event_end:
                    is_free = False
                    break

            if is_free:
                formatted_time = check_time.strftime('%d/%m %H:%M')
                daily_slots.append(formatted_time)

        if daily_slots:
            available_slots.extend(daily_slots[:max(0, num_slots_needed - len(available_slots))])
        else:
            dispatcher.utter_message(text=f"Não temos horário para {date.strftime('%d/%m')}. Verificando os próximos horários disponíveis.")

        date += timedelta(days=1)  # Move to the next day
        date_only = date.date()

    if available_slots:
        return True, available_slots
    else:
        logger.warning("No available slots found after checking multiple days.")
        return False, []

    #######################
def validate_time_def(slot_value: str, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
    api_url = "http://localhost:3010/agendamentos"
    normalized_date = normalize_date(slot_value, dispatcher)
    if normalized_date is not None:
        # Make current_date timezone-aware
        current_datetime = datetime.now(tz=normalized_date.tzinfo)
        current_date = current_datetime.date()
        normalized_date_only = normalized_date.date()

        if normalized_date_only < current_date:
            dispatcher.utter_message(text="A data fornecida já passou. Por favor, escolha uma data futura.")
            return {"time": None}
        elif normalized_date_only == current_date:
            # Date is today
            if normalized_date < current_datetime: 
                # Time provided is in the past
                dispatcher.utter_message(text="O horário fornecido já passou. Vou te mostrar outros horários disponíveis hoje.")
                # Adjust normalized_date to current time plus one hour
                normalized_date = current_datetime + timedelta(hours=1)
                # Proceed to check availability starting from adjusted time
                is_available, available_times = check_availability(normalized_date, dispatcher, api_url)
                if is_available:
                    slots_message = ', '.join(available_times)
                    dispatcher.utter_message(text=f"Próximos horários disponíveis: {slots_message}")
                    return {"time": None}
                else:
                    dispatcher.utter_message(text="Não há horários disponíveis hoje.")
                    return {"time": None}
            else:
                # Time is in the future today
                # Check if the specific time is available
                try:
                    response = requests.get(api_url)
                    response.raise_for_status()
                    events_result = response.json()
                    events = events_result.get('eventos', [])
                except Exception as e:
                    logger.error(f"Failed to fetch events: {str(e)}")
                    dispatcher.utter_message(text="Erro ao recuperar eventos do calendário.")
                    return {"time": None}

                check_time_iso = normalized_date.isoformat()
                if not any(event['dataInicial'] <= check_time_iso < event['dataFinal'] for event in events):
                    dispatcher.utter_message(f"{normalized_date.strftime('%d/%m/%Y %H:%M')} está disponível")
                    return {"time": normalized_date.isoformat(), "form_completed": True}
                else:
                    dispatcher.utter_message(text="Infelizmente, esse horário não está disponível. Vou te mostrar outros horários próximos.")
                    # Adjust normalized_date to current time plus one hour
                    normalized_date = current_datetime + timedelta(hours=1)
                    is_available, available_times = check_availability(normalized_date, dispatcher, api_url)
                    if is_available:
                        slots_message = ', '.join(available_times)
                        dispatcher.utter_message(text=f"Próximos horários disponíveis: {slots_message}")
                    return {"time": None}
        else:
            # Date is in the future
            # Proceed as normal
            if normalized_date.hour == 0 and normalized_date.minute == 0:
                # Only the date was provided; show available times for that day
                is_available, available_times = check_availability(normalized_date, dispatcher, api_url)
                if is_available:
                    slots_message = ', '.join(available_times)
                    dispatcher.utter_message(text=f"Próximos horários disponíveis em {normalized_date.strftime('%d/%m')}: {slots_message}")
                    return {"time": None}
                else:
                    dispatcher.utter_message(text=f"Não há horários disponíveis em {normalized_date.strftime('%d/%m')}.")
                    return {"time": None}
            else:
                # Specific time in future date
                try:
                    response = requests.get(api_url)
                    response.raise_for_status()
                    events_result = response.json()
                    events = events_result.get('eventos', [])
                except Exception as e:
                    logger.error(f"Failed to fetch events: {str(e)}")
                    dispatcher.utter_message(text="Erro ao recuperar eventos do calendário.")
                    return {"time": None}

                check_time_iso = normalized_date.isoformat()
                if not any(event['dataInicial'] <= check_time_iso < event['dataFinal'] for event in events):
                    dispatcher.utter_message(f"{normalized_date.strftime('%d/%m/%Y %H:%M')} está disponível")
                    return {"time": normalized_date.isoformat(), "form_completed": True}
                else:
                    dispatcher.utter_message(text="Infelizmente, esse horário não está disponível. Vou te mostrar outros horários próximos.")
                    is_available, available_times = check_availability(normalized_date, dispatcher, api_url)
                    if is_available:
                        slots_message = ', '.join(available_times)
                        dispatcher.utter_message(text=f"Próximos horários disponíveis: {slots_message}")
                    return {"time": None}
    else:
        logger.error("Failed to normalize date")
        dispatcher.utter_message(text="Data fornecida é inválida.")
    return {"time": None}
