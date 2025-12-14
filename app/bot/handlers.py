import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import messages
from app.bot.keyboards import (
    ADMIN_BACK_BTN,
    ADMIN_BTN,
    ADMIN_LIST_BTN,
    ADMIN_SHUFFLE_BTN,
    BACK_BTN,
    CHANGE_NAME_BTN,
    CANCEL_PARTICIPATION_BTN,
    PARTICIPATE_BTN,
    RECIPIENT_BTN,
    RULES_BTN,
    WISHES_BTN,
    admin_keyboard,
    main_keyboard,
)
from app.bot.states import RegistrationState
from app.config import Settings
from app.services.participants import (
    AlreadyRegisteredError,
    CannotLeaveAfterShuffleError,
    NotRegisteredError,
    NotShuffledError,
    AlreadyShuffledError,
    ParticipantService,
    RegistrationClosedError,
    ShuffleError,
)

router = Router()
log = logging.getLogger(__name__)


def is_admin(user_id: int, settings: Settings) -> bool:
    return user_id == settings.admin_tg_id


def format_contact(participant):
    if participant.username:
        return f'<a href="https://t.me/{participant.username}">@{participant.username}</a>'
    return f'<a href="tg://user?id={participant.tg_id}">написать</a>'


def format_wishes(text: str | None) -> str:
    return text.strip() if text else "Пожеланий пока нет."


async def send_participant_list(message: Message, participants):
    if not participants:
        await message.answer(messages.LIST_EMPTY)
        return

    lines = [
        messages.LIST_HEADER.format(count=len(participants)),
        *[
            f"{idx}. {html.escape(p.display_name)} — {format_contact(p)}"
            for idx, p in enumerate(participants, start=1)
        ],
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")


async def run_shuffle(
    message: Message,
    service: ParticipantService,
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    is_admin_user: bool,
):
    try:
        pairs = await service.shuffle()
    except AlreadyShuffledError:
        await message.answer(messages.SHUFFLE_ALREADY_DONE)
        return
    except ShuffleError:
        await message.answer(messages.SHUFFLE_TOO_FEW)
        return

    await session.commit()  # Ensure assignments are saved before notifications.
    await message.answer(
        messages.SHUFFLE_OK.format(count=len(pairs)),
        reply_markup=main_keyboard(True, is_admin=is_admin_user),
    )

    participants = await service.list_all()
    for participant in participants:
        try:
            await bot.send_message(
                participant.tg_id,
                messages.SHUFFLE_DONE_FOR_ALL,
                reply_markup=main_keyboard(
                    True, is_admin=participant.tg_id == settings.admin_tg_id
                ),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to notify participant %s after shuffle: %s", participant.tg_id, exc)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, settings: Settings):
    service = ParticipantService(session)
    shuffle_done = await service.is_shuffle_completed()
    await state.clear()
    await message.answer(
        messages.WELCOME,
        reply_markup=main_keyboard(shuffle_done, is_admin=is_admin(message.from_user.id, settings)),
    )


@router.message(Command("cancel"))
async def cancel_state(message: Message, state: FSMContext, session: AsyncSession, settings: Settings):
    await state.clear()
    shuffle_done = await ParticipantService(session).is_shuffle_completed()
    await message.answer(
        "Диалог сброшен.",
        reply_markup=main_keyboard(shuffle_done, is_admin=is_admin(message.from_user.id, settings)),
    )


@router.message(F.text == ADMIN_BTN)
async def admin_panel(message: Message, state: FSMContext, settings: Settings):
    if not is_admin(message.from_user.id, settings):
        await message.answer(messages.ADMIN_ONLY)
        return

    await state.clear()
    await message.answer(messages.ADMIN_MENU, reply_markup=admin_keyboard())


@router.message(F.text == ADMIN_BACK_BTN)
async def admin_back(message: Message, state: FSMContext, session: AsyncSession, settings: Settings):
    if not is_admin(message.from_user.id, settings):
        await message.answer(messages.ADMIN_ONLY)
        return

    await state.clear()
    shuffle_done = await ParticipantService(session).is_shuffle_completed()
    await message.answer(
        "Возвращаю меню.",
        reply_markup=main_keyboard(shuffle_done, is_admin=True),
    )


@router.message(F.text == PARTICIPATE_BTN)
async def participate(message: Message, state: FSMContext, session: AsyncSession, settings: Settings):
    service = ParticipantService(session)
    if await service.is_shuffle_completed():
        await message.answer(
            messages.REGISTRATION_CLOSED,
            reply_markup=main_keyboard(True, is_admin=is_admin(message.from_user.id, settings)),
        )
        return

    existing = await service.get_by_tg_id(message.from_user.id)
    if existing:
        await state.set_state(RegistrationState.waiting_for_registered_action)
        await message.answer(
            messages.REGISTERED_OPTIONS.format(name=html.escape(existing.display_name)),
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text=CHANGE_NAME_BTN)],
                    [KeyboardButton(text=CANCEL_PARTICIPATION_BTN)],
                    [KeyboardButton(text=BACK_BTN)],
                ],
                resize_keyboard=True,
                input_field_placeholder="Выбери действие",
            ),
        )
        return

    await state.set_state(RegistrationState.waiting_for_name)
    await message.answer(messages.ASK_NAME, reply_markup=ReplyKeyboardRemove())


@router.message(RegistrationState.waiting_for_name)
async def save_name(message: Message, state: FSMContext, session: AsyncSession, settings: Settings):
    service = ParticipantService(session)
    try:
        await service.register(
            tg_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            display_name=message.text or "",
        )
    except RegistrationClosedError:
        await message.answer(
            messages.REGISTRATION_CLOSED,
            reply_markup=main_keyboard(True, is_admin=is_admin(message.from_user.id, settings)),
        )
        await state.clear()
        return
    except AlreadyRegisteredError:
        await message.answer(
            messages.REGISTERED,
            reply_markup=main_keyboard(False, is_admin=is_admin(message.from_user.id, settings)),
        )
        await state.clear()
        return

    await state.clear()
    shuffle_done = await service.is_shuffle_completed()
    await message.answer(
        messages.NAME_SAVED,
        reply_markup=main_keyboard(shuffle_done, is_admin=is_admin(message.from_user.id, settings)),
    )


@router.message(RegistrationState.waiting_for_registered_action, F.text == BACK_BTN)
async def registered_back(message: Message, state: FSMContext, session: AsyncSession, settings: Settings):
    await state.clear()
    shuffle_done = await ParticipantService(session).is_shuffle_completed()
    await message.answer(
        "Ок, оставляем как есть.",
        reply_markup=main_keyboard(shuffle_done, is_admin=is_admin(message.from_user.id, settings)),
    )


@router.message(RegistrationState.waiting_for_registered_action, F.text == CHANGE_NAME_BTN)
async def registered_change_name(message: Message, state: FSMContext):
    await state.set_state(RegistrationState.waiting_for_new_name)
    await message.answer(messages.ASK_NEW_NAME, reply_markup=ReplyKeyboardRemove())


@router.message(
    RegistrationState.waiting_for_registered_action,
    ~F.text.in_([CHANGE_NAME_BTN, CANCEL_PARTICIPATION_BTN, BACK_BTN]),
)
async def registered_unknown_choice(message: Message):
    await message.answer(
        f"Выбери вариант: «{CHANGE_NAME_BTN}», «{CANCEL_PARTICIPATION_BTN}» или «{BACK_BTN}»."
    )


@router.message(RegistrationState.waiting_for_new_name)
async def save_new_name(message: Message, state: FSMContext, session: AsyncSession, settings: Settings):
    service = ParticipantService(session)
    try:
        await service.update_name(message.from_user.id, message.text or "")
    except NotRegisteredError:
        await message.answer(
            messages.NOT_REGISTERED,
            reply_markup=main_keyboard(False, is_admin=is_admin(message.from_user.id, settings)),
        )
        await state.clear()
        return

    await state.clear()
    shuffle_done = await service.is_shuffle_completed()
    await message.answer(
        messages.NAME_UPDATED,
        reply_markup=main_keyboard(shuffle_done, is_admin=is_admin(message.from_user.id, settings)),
    )


@router.message(RegistrationState.waiting_for_registered_action, F.text == CANCEL_PARTICIPATION_BTN)
async def registered_cancel_participation(
    message: Message, state: FSMContext, session: AsyncSession, settings: Settings
):
    service = ParticipantService(session)
    try:
        await service.unregister(message.from_user.id)
    except CannotLeaveAfterShuffleError:
        await message.answer(
            messages.LEAVE_FORBIDDEN,
            reply_markup=main_keyboard(True, is_admin=is_admin(message.from_user.id, settings)),
        )
        await state.clear()
        return
    except NotRegisteredError:
        await message.answer(
            messages.NOT_REGISTERED,
            reply_markup=main_keyboard(False, is_admin=is_admin(message.from_user.id, settings)),
        )
        await state.clear()
        return

    await state.clear()
    await message.answer(
        messages.LEAVE_CONFIRMED,
        reply_markup=main_keyboard(False, is_admin=is_admin(message.from_user.id, settings)),
    )


@router.message(F.text == WISHES_BTN)
async def request_wishes(message: Message, state: FSMContext, session: AsyncSession, settings: Settings):
    service = ParticipantService(session)
    participant = await service.get_by_tg_id(message.from_user.id)
    if not participant:
        await message.answer(
            messages.NOT_REGISTERED,
            reply_markup=main_keyboard(False, is_admin=is_admin(message.from_user.id, settings)),
        )
        return

    current = format_wishes(participant.wishes)
    await state.set_state(RegistrationState.waiting_for_wishes)
    await message.answer(f"{messages.ASK_WISHES}\n\nТекущие пожелания:\n{current}")


@router.message(RegistrationState.waiting_for_wishes)
async def save_wishes(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot, settings: Settings
):
    service = ParticipantService(session)
    try:
        participant = await service.update_wishes(message.from_user.id, message.text or "")
    except NotRegisteredError:
        await message.answer(
            messages.NOT_REGISTERED,
            reply_markup=main_keyboard(False, is_admin=is_admin(message.from_user.id, settings)),
        )
        await state.clear()
        return

    await state.clear()
    shuffle_done = await service.is_shuffle_completed()
    await message.answer(
        messages.WISHES_SAVED,
        reply_markup=main_keyboard(shuffle_done, is_admin=is_admin(message.from_user.id, settings)),
    )

    # Notify the Santa if assignments are done.
    santa = await service.find_santa_for(participant.id)
    if santa:
        try:
            notify_text = messages.WISHES_NOTIFY_SANTA.format(
                display=html.escape(participant.display_name),
                contact=format_contact(participant),
                wishes=html.escape(format_wishes(participant.wishes)),
            )
            await bot.send_message(chat_id=santa.tg_id, text=notify_text)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to notify santa %s: %s", santa.tg_id, exc)


@router.message(F.text == RULES_BTN)
async def show_rules(message: Message, session: AsyncSession, settings: Settings):
    service = ParticipantService(session)
    shuffle_done = await service.is_shuffle_completed()
    await message.answer(
        messages.RULES,
        reply_markup=main_keyboard(shuffle_done, is_admin=is_admin(message.from_user.id, settings)),
    )


@router.message(F.text == RECIPIENT_BTN)
async def who_is_my_recipient(message: Message, session: AsyncSession, settings: Settings):
    service = ParticipantService(session)
    try:
        recipient = await service.get_recipient_for(message.from_user.id)
    except NotRegisteredError:
        await message.answer(
            messages.NOT_REGISTERED,
            reply_markup=main_keyboard(False, is_admin=is_admin(message.from_user.id, settings)),
        )
        return
    except NotShuffledError:
        shuffle_done = await service.is_shuffle_completed()
        await message.answer(
            messages.SHUFFLE_NOT_READY,
            reply_markup=main_keyboard(shuffle_done, is_admin=is_admin(message.from_user.id, settings)),
        )
        return

    reply = messages.RECIPIENT_INFO.format(
        name=html.escape(recipient.display_name),
        contact=format_contact(recipient),
        wishes=html.escape(format_wishes(recipient.wishes)),
    )
    await message.answer(
        reply,
        parse_mode="HTML",
        reply_markup=main_keyboard(True, is_admin=is_admin(message.from_user.id, settings)),
    )


@router.message(F.text == ADMIN_SHUFFLE_BTN)
async def admin_shuffle_button(
    message: Message, session: AsyncSession, bot: Bot, settings: Settings, state: FSMContext
):
    if not is_admin(message.from_user.id, settings):
        await message.answer(messages.ADMIN_ONLY)
        return
    await state.clear()
    service = ParticipantService(session)
    await run_shuffle(
        message=message,
        service=service,
        session=session,
        bot=bot,
        settings=settings,
        is_admin_user=True,
    )


@router.message(F.text == ADMIN_LIST_BTN)
async def admin_list_button(
    message: Message, session: AsyncSession, settings: Settings, state: FSMContext
):
    if not is_admin(message.from_user.id, settings):
        await message.answer(messages.ADMIN_ONLY)
        return
    await state.clear()
    service = ParticipantService(session)
    participants = await service.list_all()
    await send_participant_list(message, participants)


@router.message(Command("shuffle"))
async def shuffle(message: Message, session: AsyncSession, bot: Bot, settings: Settings):
    if message.from_user.id != settings.admin_tg_id:
        return

    service = ParticipantService(session)
    await run_shuffle(
        message=message,
        service=service,
        session=session,
        bot=bot,
        settings=settings,
        is_admin_user=True,
    )


@router.message(Command("list"))
async def list_participants(message: Message, session: AsyncSession, settings: Settings):
    if message.from_user.id != settings.admin_tg_id:
        return

    service = ParticipantService(session)
    participants = await service.list_all()
    await send_participant_list(message, participants)
