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

START_HOUR = 7
END_HOUR = 18
MAX_SLOTS = 5
TIMEZONE = 'America/Sao_Paulo'

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

    if(slot_value):
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
    """
    Normaliza a string de entrada para um objeto datetime com fuso horário.
    """
    target_date = dateparser.parse(
        slot_value,
        settings={
            'TIMEZONE': TIMEZONE,
            'RETURN_AS_TIMEZONE_AWARE': True
        }
    )
    if target_date is None:
        dispatcher.utter_message(text="Não consegui entender a data: " + slot_value)
        logger.info("Erro ao analisar a data.")
        return None
    return target_date

def fetch_events(api_url: str, dispatcher: CollectingDispatcher) -> Optional[List[dict]]:
    """
    Obtém os eventos da API.
    """
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        events_result = response.json()
        logger.debug("Eventos obtidos com sucesso.")
        return events_result.get('eventos', [])
    except Exception as e:
        logger.error(f"Erro ao recuperar eventos: {e}")
        dispatcher.utter_message(text="Erro ao recuperar eventos do calendário.")
        return None

def parse_event_time(event: dict, timezone: pytz.timezone) -> Tuple[datetime, datetime]:
    """
    Analisa e converte os tempos de início e fim de um evento para o fuso horário especificado.
    """
    event_start = datetime.fromisoformat(event['dataInicial'].replace("Z", "+00:00")).astimezone(timezone)
    event_end = datetime.fromisoformat(event['dataFinal'].replace("Z", "+00:00")).astimezone(timezone)
    return event_start, event_end

def is_time_free(check_time: datetime, events: List[dict], timezone: pytz.timezone) -> bool:
    """
    Verifica se um horário específico está livre, dado a lista de eventos.
    """
    for event in events:
        event_start, event_end = parse_event_time(event, timezone)
        if event_start <= check_time < event_end:
            return False
    return True

def format_time(check_time: datetime) -> str:
    """
    Formata o horário para exibição.
    """
    return check_time.strftime('%d/%m %H:%M')

def get_current_datetime(timezone: pytz.timezone) -> datetime:
    """
    Obtém o datetime atual com o fuso horário especificado.
    """
    return datetime.now(tz=timezone)

def calculate_start_hour(date: datetime, current_datetime: datetime, current_date: datetime.date) -> int:
    """
    Calcula a hora de início para buscar horários disponíveis.
    """
    if date.date() == current_date:
        return max(current_datetime.hour + 1, START_HOUR)
    return START_HOUR

def handle_unavailable_time(adjusted_date: datetime, dispatcher: CollectingDispatcher, api_url: str, num_slots_needed: int = MAX_SLOTS) -> Dict[Text, Any]:
    """
    Lida com situações onde o horário desejado não está disponível, buscando novos horários.
    """
    is_available, available_times = check_availability(adjusted_date, dispatcher, api_url, num_slots_needed)
    if is_available:
        slots_message = ', '.join(available_times)
        dispatcher.utter_message(text=f"Próximos horários disponíveis: {slots_message}")
    else:
        dispatcher.utter_message(text="Não há horários disponíveis.")
    return {"time": None}

def find_available_slots(
    date: datetime, 
    events: List[dict], 
    dispatcher: CollectingDispatcher, 
    num_slots_needed: int = MAX_SLOTS
) -> List[str]:
    """
    Encontra horários disponíveis para a data especificada.
    """
    available_slots = []
    timezone = date.tzinfo
    current_datetime = get_current_datetime(timezone)
    current_date = current_datetime.date()
    date_only = date.date()

    # Ajusta a data se for uma data passada
    if date_only < current_date:
        date = current_datetime
        date_only = date.date()

    while len(available_slots) < num_slots_needed:
        daily_slots = []
        # Determina a hora de início
        start_hour = calculate_start_hour(date, current_datetime, current_date)
        if start_hour >= END_HOUR:
            date += timedelta(days=1)
            date_only = date.date()
            continue  # Próximo dia

        for hour in range(start_hour, END_HOUR):
            if len(available_slots) >= num_slots_needed:
                break
            check_time = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            if is_time_free(check_time, events, timezone):
                daily_slots.append(format_time(check_time))

        if daily_slots:
            available_slots.extend(daily_slots[:num_slots_needed - len(available_slots)])
        else:
            dispatcher.utter_message(text=f"Não temos horário para {date.strftime('%d/%m')}. Verificando os próximos horários disponíveis.")

        date += timedelta(days=1)  # Próximo dia
        date_only = date.date()

    return available_slots

def check_availability(
    date: datetime, 
    dispatcher: CollectingDispatcher, 
    api_url: str,
    num_slots_needed: int = MAX_SLOTS
) -> Tuple[bool, List[str]]:
    """
    Verifica a disponibilidade de horários a partir da data especificada.

    Retorna:
        - bool: True se houver horários disponíveis, False caso contrário.
        - List[str]: Lista de horários disponíveis.
    """
    events = fetch_events(api_url, dispatcher)
    if events is None:
        return False, []

    available_slots = find_available_slots(date, events, dispatcher, num_slots_needed)

    if available_slots:
        return True, available_slots
    else:
        logger.warning("Nenhum horário disponível encontrado após verificar múltiplos dias.")
        return False, []



def find_next_free_slots(api_url: str, dispatcher: CollectingDispatcher, max_slots: int = MAX_SLOTS) -> List[str]:
    """
    Encontra os próximos horários livres a partir de amanhã às 7h.
    """
    timezone = pytz.timezone(TIMEZONE)
    current_datetime = get_current_datetime(timezone)
    current_time = (current_datetime + timedelta(days=1)).replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    free_slots = []

    while len(free_slots) < max_slots:
        start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        last_end_time = start_of_day + timedelta(hours=START_HOUR)  

        try:
            response = requests.get(api_url + f'?dataInicial={start_of_day.isoformat()}&dataFinal={end_of_day.isoformat()}')
            response.raise_for_status()
            events_result = response.json()
            events = events_result.get('eventos', [])
            logger.debug(f"Eventos obtidos para o dia {start_of_day.strftime('%d/%m/%Y')}.")
        except Exception as e:
            logger.error(f"Falha ao buscar eventos: {str(e)}")
            dispatcher.utter_message(text="Erro ao buscar eventos para os próximos horários disponíveis.")
            break

        if not events:
            while last_end_time < end_of_day and last_end_time.hour < END_HOUR and len(free_slots) < max_slots:
                free_slots.append(format_time(last_end_time))
                last_end_time += timedelta(hours=1)
        else:
            for event in events:
                start_event, end_event = parse_event_time(event, timezone)
                while last_end_time < start_event and last_end_time.hour < END_HOUR and len(free_slots) < max_slots:
                    free_slots.append(format_time(last_end_time))
                    last_end_time += timedelta(hours=1)
                last_end_time = max(last_end_time, end_event)

            while last_end_time < end_of_day and last_end_time.hour < END_HOUR and len(free_slots) < max_slots:
                free_slots.append(format_time(last_end_time))
                last_end_time += timedelta(hours=1)

        current_time = end_of_day

    return free_slots[:max_slots]

def validate_time_def(slot_value: str, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
    """
    Valida o horário fornecido pelo usuário e interage com o dispatcher para informar a disponibilidade.
    """
    api_url = "http://localhost:3010/agendamentos"
    normalized_date = normalize_date(slot_value, dispatcher)

    if not normalized_date:
        logger.error("Falha ao normalizar a data.")
        dispatcher.utter_message(text="Data fornecida é inválida.")
        return {"time": None}

    timezone = normalized_date.tzinfo
    current_datetime = get_current_datetime(timezone)
    current_date = current_datetime.date()
    normalized_date_only = normalized_date.date()

    if normalized_date_only < current_date:
        # Data passada: ajustar para próxima hora
        adjusted_date = current_datetime + timedelta(hours=1)
        return handle_unavailable_time(adjusted_date, dispatcher, api_url)

    elif normalized_date_only == current_date:
        if normalized_date < current_datetime:
            # Horário passado hoje: ajustar para próxima hora
            dispatcher.utter_message(text="Vou te mostrar os próximos horários disponíveis:")
            adjusted_date = current_datetime + timedelta(hours=1)
            return handle_unavailable_time(adjusted_date, dispatcher, api_url)
        else:
            # Horário futuro hoje: verificar disponibilidade específica
            check_time_iso = normalized_date.isoformat()
            events = fetch_events(api_url, dispatcher)
            if events is None:
                return {"time": None}

            is_available = not any(
                event['dataInicial'] <= check_time_iso < event['dataFinal'] for event in events
            )

            if is_available:
                dispatcher.utter_message(
                    f"{normalized_date.strftime('%d/%m/%Y %H:%M')} está disponível"
                )
                return {"time": normalized_date.isoformat(), "form_completed": True}
            else:
                dispatcher.utter_message(
                    text="Infelizmente, esse horário não está disponível. Vou te mostrar outros horários próximos."
                )
                adjusted_date = current_datetime + timedelta(hours=1)
                return handle_unavailable_time(adjusted_date, dispatcher, api_url)

    else:
        # Data futura
        if normalized_date.hour == 0 and normalized_date.minute == 0:
            # Apenas a data foi fornecida: mostrar horários disponíveis para o dia
            is_available, available_times = check_availability(normalized_date, dispatcher, api_url)
            if is_available:
                slots_message = ', '.join(available_times)
                dispatcher.utter_message(
                    text=f"Próximos horários disponíveis em {normalized_date.strftime('%d/%m')}: {slots_message}"
                )
            else:
                dispatcher.utter_message(
                    text=f"Não há horários disponíveis em {normalized_date.strftime('%d/%m')}."
                )
            return {"time": None}
        else:
            # Horário específico em data futura: verificar disponibilidade
            check_time_iso = normalized_date.isoformat()
            events = fetch_events(api_url, dispatcher)
            if events is None:
                return {"time": None}

            is_available = not any(
                event['dataInicial'] <= check_time_iso < event['dataFinal'] for event in events
            )

            if is_available:
                dispatcher.utter_message(
                    f"{normalized_date.strftime('%d/%m/%Y %H:%M')} está disponível"
                )
                return {"time": normalized_date.isoformat(), "form_completed": True}
            else:
                dispatcher.utter_message(
                    text="Infelizmente, esse horário não está disponível. Vou te mostrar outros horários próximos."
                )
                return handle_unavailable_time(normalized_date, dispatcher, api_url)

    # Retorno padrão
    return {"time": None}