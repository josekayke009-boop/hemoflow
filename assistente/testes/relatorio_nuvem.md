# Assistente HemoFlow no modo nuvem (embeddings da OpenAI) - teste pelo app

## 1. O que é o HemoFlow?

*Esperado:* Seção 1 (plataforma de captação e fidelização)

*HTTP 200* - ferramentas: -

O HemoFlow é uma plataforma de captação e fidelização de doadores de sangue. Ela conecta doadores a bancos de sangue parceiros e mostra os hemocentros públicos do HEMOPE como locais de doação. O objetivo é incentivar o doador a voltar a doar, com o slogan "Doe. Volte. Salve vidas." Fonte: FAQ, seção 1. Sobre o HemoFlow.

## 2. Tenho 17 anos, posso doar sangue?

*Esperado:* Seção 2: pode com autorização do responsável; triagem decide

*HTTP 200* - ferramentas: -

Sim, você pode doar sangue com autorização do responsável legal. No cadastro do HemoFlow, é necessário informar o nome do responsável e confirmar que ele autorizou. O banco de sangue pode exigir a autorização formal no dia da doação. 

Fonte: FAQ, seção 2. Quem pode doar (orientação geral).

## 3. Quanto tempo uma mulher precisa esperar entre uma doação e outra?

*Esperado:* Seção 3: 90 dias

*HTTP 200* - ferramentas: -

Uma mulher precisa esperar no mínimo 90 dias entre uma doação e outra. 

Fonte: FAQ, seção 3. Intervalos e limites entre doações.

## 4. Sou O+, para quem posso doar?

*Esperado:* Seção 4: O+, A+, B+, AB+

*HTTP 200* - ferramentas: -

Se você é O+, pode doar para os tipos O+, A+, B+ e AB+. 

Fonte: FAQ, seção 4. Compatibilidade sanguínea (hemácias).

## 5. O que significa quando o termômetro está em Atenção?

*Esperado:* Seção 5: estoque baixando

*HTTP 200* - ferramentas: -

Quando o termômetro está em Atenção (laranja), isso significa que o estoque daquele tipo sanguíneo está baixando. Doar nos próximos dias ajuda bastante a melhorar a situação. 

Fonte: FAQ, seção 5. Termômetro da doação.

## 6. Como a minha doação é confirmada no banco de sangue?

*Esperado:* Seção 7: código de 6 dígitos

*HTTP 200* - ferramentas: -

A sua doação é confirmada no banco de sangue parceiro quando a equipe digita o código de 6 dígitos que aparece no seu app, após a triagem e a coleta. Assim, a doação passa a constar como "verificada" no seu histórico. 

Fonte: FAQ, seção 7. Registro e confirmação da doação.

## 7. Doei no HEMOPE, como registro no app?

*Esperado:* Seção 7: Perfil > Histórico, doação declarada

*HTTP 200* - ferramentas: -

Para registrar sua doação no app, vá em Perfil › Histórico de doações e use a opção "Doou em outro lugar?". Informe a data e o local da doação. Assim, ela ficará registrada como "declarada". 

Fonte: FAQ, seção 7. Registro e confirmação da doação.

## 8. Como funciona a isenção de taxa de concurso em Pernambuco?

*Esperado:* Seção 8: 3 homens / 2 mulheres em 12 meses; declaração da entidade

*HTTP 200* - ferramentas: -

Em Pernambuco, o doador regular tem isenção de taxa em concursos. Para ser considerado doador regular, é necessário ter feito no mínimo 3 doações (homens) ou 2 doações (mulheres) nos 12 meses anteriores ao edital do concurso. A comprovação da isenção é feita com a declaração emitida pela entidade coletora. O progresso nessa meta pode ser consultado no app, em Perfil › Meus direitos e conquistas. 

Fonte: FAQ, seção 8. Benefícios e direitos do doador.

## 9. Por que não consigo gerar cupom?

*Esperado:* Seção 9: precisa de doação verificada nos últimos 6 meses

*HTTP 200* - ferramentas: -

Você só pode gerar cupons se tiver pelo menos uma doação verificada pelo banco de sangue nos últimos 6 meses. Se suas doações foram declaradas, elas não liberam cupons. Verifique se atende a esses critérios. 

Fonte: FAQ, seção 9. Vantagens e cupons.

## 10. Quando posso doar de novo?

*Esperado:* Ferramenta quando_posso_doar (doador logado)

*HTTP 200* - ferramentas: quando_posso_doar

Você já pode doar novamente. Lembre-se que a decisão final é da triagem do banco de sangue. 

Fonte: seu cadastro no HemoFlow.

## 11. Como está minha meta de isenção?

*Esperado:* Ferramenta minha_meta_isencao (doador logado)

*HTTP 200* - ferramentas: minha_meta_isencao

Você cumpriu sua meta de isenção de taxa em concursos estaduais em Pernambuco, com 2 doações verificadas na janela de 12 meses. Não faltam doações para atingir a meta. Lembre-se que a comprovação oficial é a declaração emitida pela entidade coletora. 

Fonte: seu cadastro no HemoFlow.

## 12. Como está o estoque de O- no Banco Vida?

*Esperado:* Ferramenta nivel_do_estoque (nível + data, sem quantidade)

*HTTP 200* - ferramentas: nivel_do_estoque

O estoque de O- no Banco de Sangue Vida está em nível crítico. Essa informação foi atualizada em 25/11/2026. Lembre-se que esse nível é informado pelo próprio banco e não representa o estoque oficial do HEMOPE. 

Fonte: níveis informados pelos bancos parceiros.

## 13. Tomo remédio para pressão alta, posso doar?

*Esperado:* Saúde: não orienta; manda para a triagem

*HTTP 200* - ferramentas: -

Dúvidas sobre remédios, como o uso de medicamentos para pressão alta, devem ser tiradas com a triagem do hemocentro ou do banco de sangue. Eles seguirão as normas do Ministério da Saúde para avaliar sua situação. 

Fonte: FAQ, seção 2. Quem pode doar (orientação geral).

## 14. Fiz uma tatuagem mês passado, posso doar?

*Esperado:* Saúde: não orienta; manda para a triagem

*HTTP 200* - ferramentas: -

Dúvidas sobre tatuagens devem ser tiradas com a triagem do hemocentro ou do banco de sangue, que segue as normas do Ministério da Saúde. É importante verificar com eles se você pode doar. 

Fonte: FAQ, seção 2. Quem pode doar (orientação geral).

## 15. Qual vai ser a previsão do tempo amanhã em Recife?

*Esperado:* Fora do escopo: não sabe

*HTTP 200* - ferramentas: -

Não encontrei essa informação na base do HemoFlow. Para essa dúvida, procure o banco de sangue, o HEMOPE ou a equipe pela aba Ajuda do app.
Fonte: não encontrada na base do HemoFlow

## Parceiro: Como valido o cupom de um doador?

*HTTP 200*

Para validar o cupom de um cliente, abra o painel do parceiro, selecione "Validar cupom", digite o código que o cliente mostra no app e confirme. O uso do cupom fica registrado e ele não pode ser utilizado novamente. A validação requer conexão com a internet para garantir que o uso seja único. 

Fonte: FAQ, seção 14. Para parceiros (lojas, cursinhos, pré-Enem e faculdades).
