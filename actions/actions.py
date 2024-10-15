from rasa_sdk.events import AllSlotsReset,Restarted, SlotSet,UserUtteranceReverted,ConversationPaused, EventType
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from typing import Dict, Text, Any, List
from rasa_sdk import Action, Tracker
from googlesearch import search
from typing import Text
from rasa_sdk.events import EventType,ActiveLoop

import logging 
import openai


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ActionDeactivateLoop(Action):
    def name(self):
        return "action_deactivate_loop"

    async def run(self, dispatcher, tracker, domain):
        return [ActiveLoop(None), SlotSet("requested_slot", None)]

class ActionHandoverToHuman(Action):
    def name(self) -> Text:
        return "action_transferir_atendente"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Estamos te transferindo para nosso atendente, aguarde um momento... 😊")

   
        #pausa o bot, para o atendente responder
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
    
    
    
##Action responsavel por fornecer os precos baseados nas entidades e depois resetar o slot
class ActionProvidePriceAndResetSlot(Action):
    def name(self) -> Text:
        return "action_provide_price_and_reset_slot"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[SlotSet]:
        list_synonym_psico = ['psicólogo', 'psicologo', 'psicóloga', 'psicologa']
        especialista = tracker.get_slot("especialista")

        if especialista:
            especialista = especialista.lower()
            if especialista in list_synonym_psico:
                message = "O preço da consulta com o psicólogo é de R$110,00"
            elif especialista == "psiquiatra":
                message = "O preço da consulta com o psiquiatra é de R$480,00"
            else:
                message = (
                    "O preço de nossas consultas varia de especialistas. "
                    "As consultas com os psicólogos são R$110,00 e psiquiatras R$480,00."
                )
        else:
            message = (
                "O preço de nossas consultas varia de especialistas. "
                "As consultas com os psicólogos são R$110,00 e psiquiatras R$480,00."
            )

        dispatcher.utter_message(text=message)
        return [SlotSet("especialista", None)]
    
    
    
#Action para resetar o valor de time e form_completed
class ActionResetTimeSlot(Action):
    def name(self) -> Text:
        return "action_reset_slot_time"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[SlotSet]:
        return [SlotSet("time", None), SlotSet("form_completed",False)]
    

    

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

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        # Pegando o valor do slot 'feedback'
        feedback = tracker.get_slot('feedback')
        
        # Verifica se o feedback está preenchido corretamente
        if feedback:
            dispatcher.utter_message(text="Muito obrigado pelo seu feedback!")
            # Aqui você pode armazenar o feedback em um banco de dados, se desejar
            return []

        else:
            dispatcher.utter_message(text="Não recebi um feedback válido.")
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
    
            


import requests
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType
from rasa_sdk.executor import CollectingDispatcher

class AskForSlotActionEspecialista(Action):
    def name(self) -> Text:
        return "action_ask_event_form_especialista"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        buttons = []

        try:
            # Make API GET request to get the data
            response = requests.get('http://localhost:3010/medicos')
            data = response.json()

            # Extract unique categories (especialistas)
            categorias = {}
            for item in data:
                categoria_nome = item['categoria']['nome']
                categoria_id = item['categoria']['id']
                categorias[categoria_id] = categoria_nome

            # Create buttons for each unique category
            for categoria_id, categoria_nome in categorias.items():
                buttons.append({
                    "title": categoria_nome,
                    "payload": categoria_nome.lower()
                })

            dispatcher.utter_message(
                text="Qual dos nossos especialistas deseja marcar a consulta?",
                buttons=buttons
            )
        except Exception as e:
            dispatcher.utter_message(
                text="Desculpe, ocorreu um erro ao obter os especialistas. Tente novamente mais tarde."
            )

        return []

class AskForSlotAction(Action):
    def name(self) -> Text:
        return "action_ask_event_form_profissional"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        especialista = tracker.get_slot('especialista')
        buttons = []

        if especialista:
            especialista = especialista.lower()

            try:
                # Make API GET request to get the data
                response = requests.get('http://localhost:3010/medicos')
                data = response.json()

                # Filter professionals based on selected especialista
                profissionais = [
                    item for item in data
                    if item['categoria']['nome'].lower() == especialista
                ]

                if profissionais:
                    for profissional in profissionais:
                        profissional_nome = profissional['nome']
                        payload = profissional_nome.lower()
                        buttons.append({
                            "title": profissional_nome,
                            "payload": payload
                        })

                    buttons.append({
                        "title": f"Não quero agendar com {especialista}",
                        "payload": 'nenhum'
                    })

                    dispatcher.utter_message(
                        text=f"Qual {especialista} você tem preferência de consultar?",
                        buttons=buttons
                    )
                else:
                    dispatcher.utter_message(
                        text=f"Desculpe, não temos profissionais para o especialista {especialista} no momento."
                    )
            except Exception as e:
                dispatcher.utter_message(
                    text="Desculpe, ocorreu um erro ao obter os profissionais. Tente novamente mais tarde."
                )
        else:
            dispatcher.utter_message(
                text="Desculpe, não recebi o especialista desejado. Por favor, escolha corretamente."
            )

        return []
