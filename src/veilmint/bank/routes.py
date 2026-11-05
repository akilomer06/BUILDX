"""Customer API; DTOs exclude internal database properties before minimisation."""
from fastapi import APIRouter, Depends, Request, Response, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .service import Bank, BankError
from .protection import BankProtection, DESTINATION, CONTRACT_EXCLUDED_FIELDS
from ..response_inspection import capture_response


class Input(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)


class Login(Input):
    username:str=Field(min_length=3,max_length=100,pattern=r'^[A-Za-z0-9_.@+-]+$')
    password:str=Field(min_length=12,max_length=128)


class Register(Login):
    display_name:str=Field(min_length=1,max_length=60)

    @field_validator('display_name')
    @classmethod
    def nonblank(cls,value):
        if not value.strip() or any(ord(c)<32 for c in value): raise ValueError('Invalid display name')
        return value.strip()


class Beneficiary(Input):
    destination_account_id:str=Field(pattern=r'^[0-9]{12}$')
    label:str=Field(min_length=1,max_length=60)

    @field_validator('label')
    @classmethod
    def nonblank(cls,value):
        if not value.strip() or any(ord(c)<32 for c in value): raise ValueError('Invalid beneficiary label')
        return value.strip()


class Transfer(Input):
    source_account_id:str=Field(pattern=r'^[0-9]{12}$')
    destination_account_id:str=Field(pattern=r'^[0-9]{12}$')
    amount_minor:int=Field(gt=0,le=100_000_000)
    currency:str=Field(pattern='^INR$')
    idempotency_key:str=Field(min_length=8,max_length=128)


def router(settings):
    routes=APIRouter(prefix='/api/bank')
    def bank(): return Bank(settings.database_path)
    def customer(request:Request):
        user=bank().authenticate(request.cookies.get('nexus_session'))
        request.state.customer_reference=user['id']
        return user

    @routes.post('/auth/register',status_code=201)
    def register(body:Register):
        return bank().register(body.display_name,body.username,body.password)

    @routes.post('/auth/login')
    def login(body:Login,response:Response):
        token=bank().login(body.username,body.password)
        response.set_cookie('nexus_session',token,httponly=True,secure=settings.bank_secure_cookie,samesite='strict',max_age=28800,path='/api/bank')
        return {'authenticated':True,'expires_in':28800}

    @routes.post('/auth/logout')
    def logout(request:Request,response:Response):
        bank().logout(request.cookies.get('nexus_session'))
        response.delete_cookie('nexus_session',path='/api/bank',secure=settings.bank_secure_cookie,httponly=True,samesite='strict')
        return {'authenticated':False}

    @routes.get('/customers/me')
    def me(request:Request,user=Depends(customer)):
        return capture_response(request,{'customer_id':user['id'],'display_name':user['display_name'],'sandbox':True})

    @routes.get('/accounts')
    def accounts(request:Request,user=Depends(customer)): return capture_response(request,bank().accounts(user['id']))

    @routes.get('/accounts/{account_id}')
    def account(account_id:str,request:Request,user=Depends(customer)):
        source=bank().account(user['id'],account_id,source=True)
        payload={key:value for key,value in source.items() if key not in CONTRACT_EXCLUDED_FIELDS}
        result=BankProtection(settings).protect(payload)
        request.state.destination=DESTINATION
        request.state.protection=result
        request.state.kept_paths=tuple('/'+key for key in result.payload)
        request.state.account_id=source['account_id']
        request.state.source_paths=tuple('/'+key for key in sorted(source))
        request.state.contract_excluded=tuple('/'+key for key in sorted(source.keys()-payload.keys()))
        # Explicit account-audit fields enter the existing sanitizer in memory.
        # Raw account numbers and credentials are never collected by this logger.
        request.state.log_fields={key:source[key] for key in ('display_name','available_balance_minor','recent_transactions',
                                  'contact_email','customer_phone','customer_address') if key in source}
        return capture_response(request,result.payload)

    @routes.get('/accounts/{account_id}/transactions')
    def transactions(account_id:str,request:Request,user=Depends(customer),limit:int=Query(default=25,ge=1,le=100),offset:int=Query(default=0,ge=0)):
        return capture_response(request,bank().transactions(user['id'],account_id,limit,offset))

    @routes.get('/beneficiaries')
    def beneficiaries(request:Request,user=Depends(customer)): return capture_response(request,bank().beneficiaries(user['id']))

    @routes.post('/beneficiaries',status_code=201)
    def add_beneficiary(body:Beneficiary,request:Request,user=Depends(customer)):
        return capture_response(request,bank().add_beneficiary(user['id'],body.destination_account_id,body.label),201)

    @routes.post('/transfers',status_code=201)
    def transfer(body:Transfer,request:Request,user=Depends(customer)):
        BankProtection(settings).record({
            'event_type':'TRANSFER_INITIATED','endpoint':'/api/bank/transfers','method':'POST',
            'http_status':202,'correlation_id':request.state.correlation_id,'destination':'nexus_bank.transfer.v1',
            'policy_revision':None,'mode':settings.bank_mode.value,'outcome':'REQUESTED','customer_reference':user['id'],
        })
        receipt=bank().transfer(user['id'],body.source_account_id,body.destination_account_id,body.amount_minor,body.currency,body.idempotency_key)
        request.state.account_id=receipt['source']  # ownership was validated by the service
        return capture_response(request,receipt,201)

    @routes.get('/transfers/{transfer_id}')
    def receipt(transfer_id:str,request:Request,user=Depends(customer)): return capture_response(request,bank().receipt(user['id'],transfer_id))
    return routes
