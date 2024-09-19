from rasa_sdk.events import AllSlotsReset,Restarted,FollowupAction,SlotSet,UserUtteranceReverted,ConversationPaused
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from typing import Dict, Text, Any, List
from rasa_sdk import Action, Tracker
from datetime import timedelta
import requests
import logging 
import dateparser
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
import re
from helpers.utils import validate_cpf_bd, validate_cpf_value,validate_time_def,generate_random_string,find_next_free_slots,get_event_id_from_cpf,modify_event
import openai
from typing import Text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


## action


class ActionHandoverToHuman(Action):
    def name(self) -> Text:
        return "action_transferir_atendente"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Send a message to the user
        dispatcher.utter_message(text="Estamos te transferindo para nosso atendente, aguarde um momento... 😊")

        # Optionally, notify the frontend or backend system
        # For example, you might publish a message to a message queue,
        # make an API call, or set a flag in a database.

        # Return the ConversationPaused event
        return [ConversationPaused()]

# responsavel por dar um fallback, acionado pelo core fallback e configurado no config.yml, pode-se setar a % confianca para dar trigger no fallback, atualmente 0.7
class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Desculpe, não consegui entender. Pode tentar novamente?")
        logger.info("fallback triggered ")
        # Reverter a última fala do usuário
        return [UserUtteranceReverted()]

# Reseta a conversa, zerando todos slots e atencoes das historias
class ActionResetAll(Action):
    def name(self):
        return "action_reset_all"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Resetar todos os slots e o tracker
        logger.info("Conversation restarted")
        return [Restarted(), AllSlotsReset()]

#class ActionFallbackToGPT(Action):
#
#    def name(self) -> Text:
#        return "action_fallback_to_gpt"
#
#    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#        user_message = tracker.latest_message.get('text')
#        detected_intent = self.call_chatgpt_for_intent(user_message)
#
#        if detected_intent:
#           return [
#               UserUtteranceReverted(), 
#               UserUttered(
#                   text=user_message, 
#                   parse_data={
#                        "intent": {"name": detected_intent, "confidence": 1.0},#
#                        "entities": [],
#                      "text": user_message,
#                        "message_id": None,
#                        "metadata": {},
#                        "intent_ranking": [{"name": detected_intent, "confidence": 1.0}]
#                    }
#                )
#            ]
#        else:
#            dispatcher.utter_message(text="Desculpe, não consegui entender sua solicitação.")
#            return []




#Guarda o feedback gerado pelo user
class ActionStoreFeedback(Action):
    def name(self) -> Text:
        return "action_store_feedback"

    def run(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Retrieve the 'feedback' entity directly from the latest message
        feedback_entity = next(tracker.get_latest_entity_values('feedback'), None)
        
        if feedback_entity is None:
            dispatcher.utter_message(text="Desculpe, não entendi. Por favor, avalie nossa conversa com uma nota de 1 a 5.")
            return []

        try:
            feedback = float(feedback_entity)
        except ValueError:
            dispatcher.utter_message(text="Desculpe, não entendi. Por favor, use um número de 1 a 5 para avaliar.")
            return []

        if 1 <= feedback <= 5:
            dispatcher.utter_message(text="Muito obrigado pelo seu feedback!")
            # If you have a logger, you can log the feedback
            # logger.info(f"Feedback provided: {feedback}")
            return [SlotSet("feedback", feedback)]
        else:
            dispatcher.utter_message(text="A nota deve ser entre 1 e 5. Por favor, tente novamente.")
            return []

#Custom fallback, esse fallback faz com que se o fallback for gerado 3 vezes, chama o show_options e reseta a conversa
class ActionCustomFallback(Action):
    def name(self) -> str:
        return "action_custom_fallback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        fallback_count = tracker.get_slot('fallback_count') or 0.0
        

        fallback_count += 1.0


        if fallback_count >= 4.0:
            dispatcher.utter_message(response="utter_default")
            dispatcher.utter_message(response="utter_show_options")
            logger.info("Custom Fallback triggered after 3 consecutive failures")
            return [SlotSet("fallback_count", 0.0)]  
        
        dispatcher.utter_message(response="utter_ask_rephrase")
        return [SlotSet("fallback_count", fallback_count)]
    
#Cadastra o usuario no banco \
# #////////////////////////////////////  

class ActionSalvarCadastro(Action):
    def name(self) -> Text:
        return "action_salvar_cadastro"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        nome = tracker.get_slot("nome")
        email = tracker.get_slot("email")
        cpf = tracker.get_slot("cpf")
        telefone = tracker.get_slot("telefone")

        url = "http://localhost:3010/usuario/cadastro"
        data = {
            "name": nome,
            "email": email,
            "cpf": cpf,
            "phoneNumber": telefone,
            "adminId": 1
        }
        try:
            response = requests.post(url, json=data)
            if 200 <= response.status_code < 300:
                logger.info(f"Usuário de email : {email} registrado com sucesso.")
                return [SlotSet("login_sucess", True)]
            
            else:
                dispatcher.utter_message(text="Falha ao cadastrar o usuário. Tente novamente.")
                logger.warning(f"Falha ao cadastrar usuario: {email}. Status code: {response.status_code}")
                return [SlotSet("login_sucess", False)]
        except requests.exceptions.RequestException as e:
            logger.error("Erro de conexão com o serviço de registro: %s", str(e))
            return [SlotSet("login_sucess", False)]

####VALIDANDO FORMS
####VALIDANDO FORMS


### As classes de validação precisam receber os 5 parametros mesmo nao usando todos, como tracker ou domain.
### As classes de validação servem para validar os slots dos formularios 
class ValidateNome(FormValidationAction):
    def name(self):
        return "validate_cadastro_form"

    def validate_nome(
            self, 
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],     
            ) -> Dict[Text, Any]:
            # Expressão regular ajustada para aceitar acentos
            if not re.match(r'^[A-Za-zÀ-ÖØ-öø-ÿ\s]+$', slot_value):
                dispatcher.utter_message(text="O nome deve conter apenas letras.")
                return {"nome": None}
            elif len(slot_value) <= 2:
                dispatcher.utter_message(text="O nome deve ter mais de 2 caracteres.")
                return {"nome": None}
            else:
                return {"nome": slot_value}
        
    def validate_cpf(
            self, 
            slot_value: Any,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: DomainDict
            ) -> Dict[Text, Any]:
        return validate_cpf_value(slot_value, dispatcher)   
    
    
    def validate_telefone(
        self, 
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
        ) -> Dict[Text, Any]:
        
        pattern = re.compile(r'^\(\d{2}\) \d{5}-\d{4}$')
        
        if pattern.match(slot_value):
            logger.info("Telefone validado com sucesso.")
            return {"telefone": slot_value}
        else:
            dispatcher.utter_message(text="O telefone deve estar no formato (00) 00000-0000.")
            return {"telefone": None}
        
        
    def validate_email(
        self, 
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,     
        ) -> Dict[Text, Any]:
        # Expressão regular para validar formato de e-mail
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

        if re.match(email_pattern, slot_value):
            logger.info("email validated")
            return {"email": slot_value}
        else:
            dispatcher.utter_message(text="Insira um endereço de e-mail válido.")
            return {"email": None}
               
####ACTION PARA LIDAR COM PAGAMENTOS PIX         
class ActionGeneratePixCode(Action):
    def name(self):
        return "action_generate_pix_code"

    def run(self, dispatcher, tracker, domain):
        valor = tracker.get_slot("valor_pagamento")  # Supondo que você tenha capturado o valor do pagamento
        user_info = tracker.get_slot("user_info")  # Informações do usuário (nome, CPF, etc.)

        # Exemplo com a API da Gerencianet (adaptar conforme a API do provedor escolhido)
        headers = {
            "Authorization": "Bearer sua_chave_de_acesso",
            "Content-Type": "application/json"
        }
        data = {
            "valor": {
                "original": str(valor)
            },
            "chave": "sua_chave_pix",  # Sua chave Pix cadastrada
            "solicitacaoPagador": "Pagamento de compra"
        }

        try:
            response = requests.post("https://api.gerencianet.com.br/v2/cob", headers=headers, json=data)
            response.raise_for_status() 
            
            # Convertendo a resposta para JSON
            pix_data = response.json()

            # Verificando se o campo 'location' está presente na resposta
            if 'location' in pix_data:
                pix_code = pix_data['location']
                dispatcher.utter_message(text=f"Aqui está seu código Pix: {pix_code}")
                return [SlotSet("pix_code", pix_code)]
            else:
                # Se a chave 'location' não estiver presente, tratamos como um erro
                dispatcher.utter_message(text="Ocorreu um erro ao gerar o código Pix. Tente novamente mais tarde.")
                return []

        except requests.exceptions.HTTPError as http_err:
            dispatcher.utter_message(text=f"Erro HTTP ao tentar gerar o código Pix: {http_err}")
            return []
        except requests.exceptions.ConnectionError as conn_err:
            dispatcher.utter_message(text=f"Erro de conexão ao tentar acessar o serviço de pagamento: {conn_err}")
            return []
        except requests.exceptions.Timeout as timeout_err:
            dispatcher.utter_message(text=f"A requisição para gerar o código Pix excedeu o tempo limite: {timeout_err}")
            return []
        except requests.exceptions.RequestException as req_err:
            dispatcher.utter_message(text=f"Ocorreu um erro ao tentar gerar o código Pix: {req_err}")
            return []
        except Exception as e:
            dispatcher.utter_message(text=f"Ocorreu um erro inesperado: {e}")
            return []
            
class ActionConfirmPixPayment(Action):
    def name(self):
        return "action_confirm_pix_payment"

    def run(self, dispatcher, tracker, domain):
        payment_id = tracker.get_slot("payment_id")  # ID da transação Pix (txid)

        headers = {
            "Authorization": "Bearer sua_chave_de_acesso",
            "Content-Type": "application/json"
        }

        try:
            # Fazendo a requisição para verificar o status do pagamento
            response = requests.get(f"https://api.gerencianet.com.br/v2/cob/{payment_id}", headers=headers)
            response.raise_for_status()
            payment_data = response.json()

            status = payment_data.get('status', '')
            if status == 'CONCLUIDA':  # Verificar a documentação do seu provedor
                dispatcher.utter_message(text="O pagamento foi confirmado com sucesso!")
                return [SlotSet("payment_status", "confirmed")]
            else:
                dispatcher.utter_message(text="O pagamento ainda não foi confirmado. Tente novamente mais tarde.")
                return [SlotSet("payment_status", "pending")]

        except requests.exceptions.RequestException as e:
            dispatcher.utter_message(text=f"Ocorreu um erro ao verificar o status do pagamento: {e}")
            return []          
           
           
           
            
#Valida o CPF para excluir a consulta

class ValidateCPFActionDelete(FormValidationAction):
    def name(self):
        return "validate_delete_event_form"

    def validate_cpf(
        self, 
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,     
        ) -> Dict[Text,Any]:
        return validate_cpf_bd(slot_value,dispatcher)
    


class ValidateCPFActionDelete(FormValidationAction):
    def name(self):
        return "validate_modify_event_form"

    def validate_cpf(
        self, 
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,     
        ) -> Dict[Text,Any]:
        return validate_cpf_bd(slot_value,dispatcher)
    
    def validate_time(self, 
                      slot_value: Any,
                      dispatcher: CollectingDispatcher,
                      tracker: Tracker,
                      domain: Dict) -> Dict[Text, Any]:
        return validate_time_def(slot_value, dispatcher)
  


    


#Valida o cpf do usuario, e o horario para marcar a consulta


class ValidateCPFActionEvent(FormValidationAction):
    def name(self):
        return "validate_event_form"

    def validate_cpf(
        self, 
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,     
        ) -> Dict[Text,Any]:
        return validate_cpf_bd(slot_value,dispatcher)
    
    def validate_time(self, 
                      slot_value: Any,
                      dispatcher: CollectingDispatcher,
                      tracker: Tracker,
                      domain: Dict) -> Dict[Text, Any]:
        return validate_time_def(slot_value, dispatcher)
  





#Ação que é responsavel por adicionar a consulta no banco, com o respectivo usuario
class ValidateAndAddEvent(Action):
    def name(self) -> Text:
        return "action_add_event"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        time_str = tracker.get_slot('time')
        cpf_user = tracker.get_slot('cpf')
        

        target_date = dateparser.parse(time_str, settings={'TIMEZONE': 'America/Sao_Paulo', 'RETURN_AS_TIMEZONE_AWARE': True})
        if not target_date:
            dispatcher.utter_message(text="Formato de data e hora incorreto. Por favor, tente novamente.")
            return [SlotSet("time", None), FollowupAction("action_listen")]
    
        new_end_time = target_date + timedelta(hours=1)
        
        string_length = 10  
        random_string = generate_random_string(string_length)
        
        start_time= target_date.isoformat()
        new_end_time_str = new_end_time.isoformat()

        try:
            url = "http://localhost:3010/agendamento/cadastrar"
            data = {
                "codAgendamento": random_string,
                "cpfUser": cpf_user,
                "nomeUser": "vands",
                "dataInicial": start_time,
                "dataFinal": new_end_time_str
            }
            response = requests.post(url, json=data)
            if 200 <= response.status_code < 300:
                dispatcher.utter_message(text="Consulta marcada!")
                logger.info("Appointment created")  
                return [SlotSet("form_completed", False),SlotSet("time", None),SlotSet("event_completed", True), SlotSet("event_id", None),SlotSet("cpf", None)]
            else:
                dispatcher.utter_message(text="Falha ao cadastrar o usuário. Tente novamente.")
                logger.warning("Fail to appoint.")
                return [SlotSet("time", None), SlotSet("cpf", None)]
            
        except requests.exceptions.RequestException as e:
            #fazer um log aki
            dispatcher.utter_message(text="Erro ao conectar ao serviço de cadastro.")
            logger.error("Error to connect to service")
            return [SlotSet("time", None), SlotSet("event_id", None), SlotSet("cpf", None)]
        except Exception as e:
            logger.error("Error to connect to service")
            dispatcher.utter_message(text=f"Não foi possível adicionar o evento: {e}")
            return [SlotSet("time", None), SlotSet("event_id", None), SlotSet("cpf", None)]
        

# Ação responsável por buscar no calendario os 5 próximos horários livres
class ActionFindFreeSlots(Action):
    def name(self) -> Text:
        return "action_find_free_slots"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        api_url = "http://localhost:3010/agendamentos"
        free_slots = find_next_free_slots(api_url)

        if free_slots:
            dispatcher.utter_message(text=f"Os próximos horários disponíveis são: {', '.join(free_slots)}")
            return [SlotSet("free_slots", free_slots),SlotSet("time", None)]
        else:
            dispatcher.utter_message(text="Nenhum horário disponível dentro do intervalo especificado.")
            return [SlotSet("free_slots", []),SlotSet("time", None)]


#Action responsavel por modificar a data do evento(consulta)
class ModifyGoogleCalendarEvent(Action):
    def name(self) -> str:
        return "action_modify_event_form"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        new_start_time_str = tracker.get_slot('time')
        cpf_user = tracker.get_slot('cpf')

        event_id, error_message = get_event_id_from_cpf(cpf_user)
        print(event_id)
        if not event_id:
            dispatcher.utter_message(text=error_message)
            return []

        try:
            target_date = dateparser.parse(
                new_start_time_str,
                settings={
                    'TIMEZONE': 'America/Sao_Paulo',
                    'RETURN_AS_TIMEZONE_AWARE': True
                }
            )
            if not target_date:
                dispatcher.utter_message(text="Formato de data e hora incorreto. Por favor, tente novamente.")
                return [SlotSet("time", None), FollowupAction("action_listen")]

            new_end_time = target_date + timedelta(hours=1)
            new_start_time_str = target_date.isoformat()
            new_end_time_str = new_end_time.isoformat()

            if modify_event(event_id, new_start_time_str, new_end_time_str):
                dispatcher.utter_message(text="Mudança de consulta concluída com sucesso!")
                return [
                    SlotSet("form_completed", False),
                    SlotSet("event_modify_completed", True),
                    SlotSet("cpf", None),
                    SlotSet("event_id", None),
                    SlotSet("time", None)
                ]
            else:
                dispatcher.utter_message(text="Não conseguimos mudar sua consulta de data!")
                return [
                    SlotSet("event_modify_completed", False),
                    SlotSet("cpf", None),
                    SlotSet("event_id", None),
                    SlotSet("time", None)
                ]

        except ValueError as e:
            dispatcher.utter_message(text=f"Erro ao processar as datas: {str(e)}")
            logger.error(f"Error processing dates: {e}")

        return [
            SlotSet("cpf", None),
            SlotSet("event_id", None),
            SlotSet("time", None)
        ]

    
#Action responsavel por excluir o evento(consulta) 
class ActionDeleteGoogleCalendarEvent(Action):
    def name(self):
        return "action_delete_event_form"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        
        cpf_user = tracker.get_slot('cpf')
        event_id, error_message = get_event_id_from_cpf(cpf_user)
        
        if not event_id:
            dispatcher.utter_message(text=error_message)
            return [SlotSet("event_delete_completed", False), SlotSet("cpf", None)]

        
        url_delete = f"http://localhost:3010/agendamento/deletar/{event_id}"
        try:
            response_delete = requests.delete(url_delete)
            if 200 <= response_delete.status_code < 300:
                dispatcher.utter_message(text="Consulta cancelada com sucesso!")
                logger.info(f"Appointment {event_id} successfully cancelled.")
                return [SlotSet("event_delete_completed", True), SlotSet("cpf", None),SlotSet("event_id",None)]
            else:
                dispatcher.utter_message(text="Parece que não conseguimos cancelar sua consulta, tente mais tarde novamente.")
                logger.warning(f"Failed to delete event {event_id} from local database: {response_delete.status_code}")
                return [SlotSet("event_delete_completed", False), SlotSet("cpf", None),SlotSet("event_id",None)]
        except Exception as e:
            dispatcher.utter_message(text="Erro ao deletar a consulta, tente novamente mais tarde!")
            logger.error(f"Failed to communicate with local database for deleting event {event_id}: {str(e)}")
            return [SlotSet("event_delete_completed", False), SlotSet("cpf", None),SlotSet("event_id",None)]
            
        


