from rasa_sdk.events import AllSlotsReset,Restarted,FollowupAction, SlotSet,UserUtteranceReverted,ConversationPaused, EventType
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker
from typing import Dict, Text, Any, List
from rasa_sdk import Action, Tracker
from googlesearch import search
from typing import Text

import logging 
import openai


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



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
    
            



class AskForSlotActionEspecialista(Action):
    def name(self) -> Text:
        return "action_ask_event_form_especialista"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        buttons=[]
        buttons.append({"title": 'Psiquiatra' , "payload": 'psiquiatra'})
        buttons.append({"title": 'Psicóloga' , "payload": 'psicóloga'})
        dispatcher.utter_message(text="Qual dos nossos especialista deseja marcar a consulta?",buttons=buttons)
        return []  

class AskForSlotAction(Action):
    def name(self) -> Text:
        return "action_ask_event_form_profissional"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        list_syn_psicologos = ['psicologo', 'psicologa', 'psicólogo', 'psicóloga']
        especialista = tracker.get_slot('especialista')
        buttons = []

        if especialista:
            especialista = especialista.lower()
            if especialista == 'psiquiatra':    
                buttons.append({"title": 'Psiquiatra Dr. João', "payload": 'joao'})
                buttons.append({"title": 'Psiquiatra Dr. Pedro', "payload": 'pedro'})
                buttons.append({"title": 'Não quero agendar com psiquiatra', "payload": 'nenhum'})

                dispatcher.utter_message(
                    text="Qual psiquiatra você tem preferência de consultar?", 
                    buttons=buttons
                )
            elif especialista in list_syn_psicologos:
                buttons.append({"title": 'Psicóloga Maria', "payload": 'maria'})
                buttons.append({"title": 'Psicóloga Ana', "payload": 'ana'})
                buttons.append({"title": 'Não quero agendar com psicólogo', "payload": 'nenhum'})

                dispatcher.utter_message(
                    text="Qual psicólogo você tem preferência de consultar?", 
                    buttons=buttons
                )
            else:
                dispatcher.utter_message(
                    text="Desculpe, não entendi o especialista escolhido. Por favor, selecione corretamente."
                )
        else:
            dispatcher.utter_message(
                text="Desculpe, não recebi o especialista desejado. Por favor, escolha corretamente."
            )

        return []

