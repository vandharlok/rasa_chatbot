from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction
from typing import Dict, Text, Any
from rasa_sdk.interfaces import Tracker
from rasa_sdk.types import DomainDict
from helpers.utils import validate_cpf_bd, validate_cpf_value,validate_time_def

import re
import logging 


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
    
    def validate_especialista(
        self, 
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,     
        ) -> Dict[Text,Any]:
        
        names=['psicóloga','psiquiatra','psicologo','psicologa','psicólogo']
        if slot_value.lower() in names:
            return {"especialista": slot_value.lower()}
        else:
            dispatcher.utter_message(text="Desculpe, não entendi. Por favor, escolha uma opção válida para especialista.")
            return {"especialista": None}
        
    def validate_profissional(
        self, 
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,     
        ) -> Dict[Text,Any]:
        
        names=['pedro','maria','ana','joao']
        if slot_value.lower() in names:
            return {"profissional": slot_value.lower()}
        elif slot_value.lower() == 'nenhum':
            return {"especialista": None,"profissional":None}
        else:
            dispatcher.utter_message(text="Desculpe, não entendi. Por favor, escolha uma opção válida para especialista.")
            return {"profissional": None}